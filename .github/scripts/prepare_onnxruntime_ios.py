"""Prepare the complete iOS spec repository with pinned ONNX Runtime and Sentry metadata."""

import argparse
import base64
import hashlib
import io
import json
import plistlib
import shutil
import subprocess
import tomllib
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath


VERSION = "1.22.0"
PACKAGE_URL = (
    "https://api.nuget.org/v3-flatcontainer/microsoft.ml.onnxruntime/"
    f"{VERSION}/microsoft.ml.onnxruntime.{VERSION}.nupkg"
)
# NuGet's x-ms-meta-SHA512 for Microsoft.ML.OnnxRuntime 1.22.0.
PACKAGE_SHA512 = "zb3eqkL6hHPGzZgArsuTH9VWdUs4ooKTJHBXF6ZZfQsPvzModaAEv3u69zwtqKuwUJ/DPc8i+uKoyXMzdwqrPg=="
# The repository commit recorded in Microsoft's NuGet package.
SOURCE_COMMIT = "f217402897f40ebba457e2421bc0a4702771968e"
SOURCE_REPOSITORY = "https://github.com/ROCm/onnxruntime.git"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PODSPEC_DIRECTORY = REPOSITORY_ROOT / "app/ios/podspecs"
SENTRY_VERSION = "8.49.2"
# CocoaPods/Specs blob 056b47ca46d6eb2422ce7d593e7dc06a74bd74a2, normalized to LF.
SENTRY_PODSPEC_SHA256 = "3dc2aaf5b7d9249a1930dc0ba3034eac9fb79add744c082b7123994d0a4828c0"


def git(directory, *arguments):
    return subprocess.check_output(
        ["git", "-C", str(directory), *arguments], text=True,
    ).strip()


def verify_package(package, expected_sha512=None):
    with Path(package).open("rb") as stream:
        actual = base64.b64encode(hashlib.file_digest(stream, "sha512").digest()).decode()
    if actual != (expected_sha512 or PACKAGE_SHA512):
        raise ValueError("ONNX Runtime NuGet SHA512 mismatch")
    with zipfile.ZipFile(package) as archive:
        name = next(name for name in archive.namelist() if name.lower().endswith(".nuspec"))
        metadata = ET.fromstring(archive.read(name))
        namespace = {"n": metadata.tag.split("}")[0][1:]}
        version = metadata.find("n:metadata/n:version", namespace).text
        commit = metadata.find("n:metadata/n:repository", namespace).get("commit")
        if version != VERSION or commit != SOURCE_COMMIT:
            raise ValueError("ONNX Runtime NuGet version or source commit mismatch")


def download_package(destination):
    if not destination.exists():
        temporary = destination.with_suffix(".download")
        with urllib.request.urlopen(PACKAGE_URL, timeout=120) as response:
            with temporary.open("wb") as stream:
                shutil.copyfileobj(response, stream)
        verify_package(temporary)
        temporary.replace(destination)
    verify_package(destination)


def checkout_source(directory):
    if not (directory / ".git").exists():
        directory.mkdir(parents=True, exist_ok=True)
        git(directory, "init", "--quiet")
        git(directory, "remote", "add", "origin", SOURCE_REPOSITORY)
        git(directory, "-c", "fetch.fsckObjects=true", "fetch", "--depth=1", "--filter=blob:none", "origin", SOURCE_COMMIT)
        git(directory, "sparse-checkout", "init", "--cone")
        git(directory, "sparse-checkout", "set", "objectivec")
        git(directory, "checkout", "--detach", "FETCH_HEAD")
    verify_source(directory)


def verify_source(directory):
    if git(directory, "rev-parse", "HEAD") != SOURCE_COMMIT:
        raise ValueError("ONNX Runtime source commit mismatch")
    if (directory / "VERSION_NUMBER").read_text().strip() != VERSION:
        raise ValueError("ONNX Runtime source version mismatch")
    if git(directory, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("ONNX Runtime source checkout must be pristine")


def extract_ios_framework(package, destination):
    with zipfile.ZipFile(package) as nuget:
        contents = nuget.read("runtimes/ios/native/onnxruntime.xcframework.zip")
        license_text = nuget.read("LICENSE")
    with zipfile.ZipFile(io.BytesIO(contents)) as archive:
        root = "onnxruntime.xcframework"
        info = plistlib.loads(archive.read(f"{root}/Info.plist"))
        libraries = [library for library in info["AvailableLibraries"] if
                     library["SupportedPlatform"] == "ios" and
                     library.get("SupportedPlatformVariant") in (None, "simulator")]
        identifiers = {library["LibraryIdentifier"] for library in libraries}
        if identifiers != {"ios-arm64", "ios-arm64_x86_64-simulator"}:
            raise ValueError("ONNX Runtime package must contain device and simulator slices")
        for entry in archive.infolist():
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or ".." in path.parts or "\\" in entry.filename:
                raise ValueError("Invalid path in ONNX Runtime framework archive")
            if len(path.parts) < 2 or path.parts[0] != root or path.parts[1] not in identifiers:
                continue
            target = destination.joinpath(*path.parts)
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(entry))
                mode = (entry.external_attr >> 16) & 0o777
                if mode:
                    target.chmod(mode)
        info["AvailableLibraries"] = libraries
        (destination / root / "Info.plist").write_bytes(plistlib.dumps(info))
        for library in libraries:
            binary = destination / root / library["LibraryIdentifier"] / library["BinaryPath"]
            if not binary.is_file() or binary.stat().st_size == 0:
                raise ValueError("ONNX Runtime framework binary is missing")
        headers = destination / root / "ios-arm64/onnxruntime.framework/Headers"
        if not (headers / "onnxruntime_c_api.h").is_file():
            raise ValueError("ONNX Runtime framework headers are missing")
        shutil.copytree(headers, destination / "Headers", dirs_exist_ok=True)
    (destination / "LICENSE").write_bytes(license_text)


def archive_pod(directory, output):
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(directory).as_posix())


def prepare_specs(package, source, output, podspec_directory=PODSPEC_DIRECTORY):
    verify_package(package)
    verify_source(source)
    sentry_spec = (podspec_directory / "Sentry.podspec.json").read_text(encoding="utf-8")
    if hashlib.sha256(sentry_spec.encode("utf-8")).hexdigest() != SENTRY_PODSPEC_SHA256:
        raise ValueError("Sentry podspec SHA256 mismatch")
    sentry = json.loads(sentry_spec)
    if sentry["name"] != "Sentry" or sentry["version"] != SENTRY_VERSION:
        raise ValueError("Sentry podspec version mismatch")
    pod_root = output / "pods"
    c_pod = pod_root / "onnxruntime-c"
    c_pod.mkdir(parents=True, exist_ok=True)
    extract_ios_framework(package, c_pod)
    objc_pod = pod_root / "onnxruntime-objc"
    shutil.copytree(source / "objectivec", objc_pod / "objectivec", dirs_exist_ok=True)
    shutil.copyfile(source / "LICENSE", objc_pod / "LICENSE")
    spec_repo = output / "specs.git"
    archives = output / "archives"
    archives.mkdir(parents=True, exist_ok=True)
    for name in ("onnxruntime-c", "onnxruntime-objc"):
        spec = json.loads((podspec_directory / f"{name}.podspec.json").read_text(encoding="utf-8"))
        if spec["name"] != name or spec["version"] != VERSION:
            raise ValueError("ONNX Runtime podspec version mismatch")
        archive = archives / f"{name}-{VERSION}.zip"
        archive_pod(pod_root / name, archive)
        with archive.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        spec["source"] = {"http": archive.resolve().as_uri(), "sha256": digest}
        path = spec_repo / "Specs" / name / VERSION / f"{name}.podspec.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    sentry_path = spec_repo / "Specs/Sentry" / SENTRY_VERSION / "Sentry.podspec.json"
    sentry_path.parent.mkdir(parents=True, exist_ok=True)
    sentry_path.write_text(sentry_spec, encoding="utf-8")
    if not (spec_repo / ".git").exists():
        git(spec_repo, "init", "--quiet")
    git(spec_repo, "add", "--", "Specs")
    git(spec_repo, "-c", "user.name=Animeko dependency preparation", "-c", "user.email=dependency-build@localhost",
        "-c", "commit.gpgsign=false", "commit", "--quiet", "--allow-empty", "-m", f"ONNX Runtime {VERSION} and Sentry {SENTRY_VERSION} iOS pods")
    return spec_repo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--github-env", type=Path)
    args = parser.parse_args()
    configured = tomllib.loads((REPOSITORY_ROOT / "gradle/libs.versions.toml").read_text(encoding="utf-8"))["versions"]["onnxruntime"]
    if configured != VERSION:
        raise ValueError("Update the pinned iOS dependency metadata for the configured ONNX Runtime version")
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    package = args.package or args.output / f"onnxruntime-{VERSION}.nupkg"
    if args.package is None:
        download_package(package)
    source = args.source_dir or args.output / "source"
    if args.source_dir is None:
        checkout_source(source)
    repo = prepare_specs(package, source, args.output)
    if args.github_env:
        with args.github_env.open("a", encoding="utf-8") as stream:
            stream.write(f"ANI_ONNXRUNTIME_SPEC_REPO={repo.as_uri()}\n")
    print(f"Prepared ONNX Runtime {VERSION} device and simulator pods and Sentry {SENTRY_VERSION} metadata: {repo}")


if __name__ == "__main__":
    main()
