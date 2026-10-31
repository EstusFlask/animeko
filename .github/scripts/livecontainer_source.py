"""Publish one stable LiveContainer feed from published IPA release assets."""

import argparse
import json
import plistlib
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

SOURCE_TAG = "livecontainer-source"
BUNDLE_IDENTIFIER = "org.animeko.animeko"


def gh(*args):
    return subprocess.check_output(["gh", *args], text=True)


def inspect_ipa(path, *, download_url, date):
    with zipfile.ZipFile(path) as archive:
        infos = [name for name in archive.namelist() if re.fullmatch(r"Payload/[^/]+\.app/Info\.plist", name)]
        if len(infos) != 1:
            raise ValueError("IPA must contain exactly one application")
        info = plistlib.loads(archive.read(infos[0]))
    if info.get("CFBundleIdentifier") != BUNDLE_IDENTIFIER:
        raise ValueError("IPA bundle identifier is not Animeko")
    return {
        "version": str(info["CFBundleShortVersionString"]),
        "buildVersion": str(info["CFBundleVersion"]),
        "date": date,
        "downloadURL": download_url,
        "size": path.stat().st_size,
        "minOSVersion": info.get("MinimumOSVersion", "16.0"),
        "localizedDescription": f"Animeko {info['CFBundleShortVersionString']} for iOS.",
    }


def release_version(repository, release, directory):
    if release["draft"] or release["prerelease"] or release["tag_name"] == SOURCE_TAG:
        return None
    assets = release.get("assets", [])
    ipas = [asset for asset in assets if asset["name"].lower().endswith(".ipa")]
    if not ipas:
        return None
    if len(ipas) != 1:
        raise ValueError(f"Release {release['tag_name']} has multiple IPA assets")
    ipa = ipas[0]
    tag = release["tag_name"]
    version = None
    if any(asset["name"] == "ios-release.json" for asset in assets):
        gh("release", "download", tag, "--repo", repository, "--pattern", "ios-release.json", "--dir", str(directory), "--clobber")
        version = json.loads((directory / "ios-release.json").read_text())
        if version.get("downloadURL") != ipa["browser_download_url"] or version.get("size") != ipa["size"]:
            version = None
    if version is None:
        gh("release", "download", tag, "--repo", repository, "--pattern", ipa["name"], "--dir", str(directory), "--clobber")
        version = inspect_ipa(directory / ipa["name"], download_url=ipa["browser_download_url"], date=release["published_at"])
    for key in ("version", "buildVersion", "date", "downloadURL", "size", "minOSVersion"):
        if key not in version:
            raise ValueError(f"Missing IPA metadata: {key}")
    if not re.fullmatch(r"\d+(?:\.\d+){1,2}", version["version"]):
        raise ValueError("Release version must be numeric and contain no development suffix")
    if not re.fullmatch(r"\d+(?:\.\d+){0,2}", version["buildVersion"]):
        raise ValueError("Release build number must be numeric")
    return version


def build_source(repository, versions):
    if not versions:
        raise ValueError("No published Animeko IPA releases found")
    def version_key(version):
        return (tuple(int(n) for n in version["version"].split(".")),
                tuple(int(n) for n in version["buildVersion"].split(".")))
    versions = sorted(versions, key=version_key, reverse=True)
    latest = versions[0]
    icon = f"https://raw.githubusercontent.com/{repository}/main/app/ios/Animeko/Assets.xcassets/AppIcon.appiconset/512.png"
    return {
        "name": "Animeko",
        "identifier": "com.estusflask.animeko.emby-test",
        "sourceURL": f"https://github.com/{repository}/releases/download/{SOURCE_TAG}/source.json",
        "website": f"https://github.com/{repository}/releases",
        "iconURL": icon,
        "apps": [{
            "name": "Animeko",
            "bundleIdentifier": BUNDLE_IDENTIFIER,
            "developerName": "OpenAni contributors / EstusFlask",
            "localizedDescription": "Animeko for iOS. Install and update with LiveContainer.",
            "iconURL": icon,
            "appPermissions": {"entitlements": [], "privacy": {"NSCameraUsageDescription": "扫描二维码登录"}},
            **latest,
            "versionDate": latest["date"],
            "versions": versions,
        }],
        "news": [],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("dist/source.json"))
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        parser.error("Invalid GitHub repository")
    pages = json.loads(gh("api", f"repos/{args.repository}/releases", "--paginate", "--slurp"))
    versions = []
    with tempfile.TemporaryDirectory(prefix="animeko-source-") as temporary:
        for release in [item for page in pages for item in page]:
            version = release_version(args.repository, release, Path(temporary))
            if version is not None:
                versions.append(version)
    source = build_source(args.repository, versions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(source, ensure_ascii=False, indent=2) + "\n")
    if args.publish:
        tag_exists = subprocess.run(["gh", "release", "view", SOURCE_TAG, "--repo", args.repository], capture_output=True).returncode == 0
        if not tag_exists:
            gh("release", "create", SOURCE_TAG, "--repo", args.repository, "--target", "main", "--title", "LiveContainer Source", "--prerelease", "--latest=false", "--notes", "Persistent Animeko source. Add its source.json URL to LiveContainer once.")
        gh("release", "upload", SOURCE_TAG, "--repo", args.repository, str(args.output), "--clobber")
    print(source["sourceURL"])


if __name__ == "__main__":
    main()
