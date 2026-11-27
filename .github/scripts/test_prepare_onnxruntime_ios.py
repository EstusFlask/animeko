import base64
import hashlib
import importlib.util
import io
import json
import plistlib
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("prepare_onnxruntime_ios", Path(__file__).with_name("prepare_onnxruntime_ios.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PrepareOnnxruntimeIosTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="animeko-ort-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "objectivec").mkdir()
        (self.source / "objectivec/ort_env.mm").write_bytes(b"// Objective-C source\n")
        (self.source / "LICENSE").write_text("MIT\n")
        (self.source / "VERSION_NUMBER").write_text(module.VERSION)
        module.git(self.source, "init", "--quiet")
        module.git(self.source, "add", ".")
        module.git(self.source, "-c", "user.name=Test", "-c", "user.email=test@localhost",
                   "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Fixture")
        commit = module.git(self.source, "rev-parse", "HEAD")
        self.commit_patch = patch.object(module, "SOURCE_COMMIT", commit)
        self.commit_patch.start()
        self.addCleanup(self.commit_patch.stop)
        self.package = self.root / "runtime.nupkg"

    def package_fixture(self, missing_simulator=False, bad_path=False, commit=None):
        content = io.BytesIO()
        libraries = []
        with zipfile.ZipFile(content, "w") as archive:
            for identifier, variant in [("ios-arm64", None), ("ios-arm64_x86_64-simulator", "simulator")]:
                if variant and missing_simulator:
                    continue
                library = {"LibraryIdentifier": identifier, "SupportedPlatform": "ios",
                           "BinaryPath": "onnxruntime.framework/onnxruntime"}
                if variant:
                    library["SupportedPlatformVariant"] = variant
                libraries.append(library)
                prefix = f"onnxruntime.xcframework/{identifier}/onnxruntime.framework"
                archive.writestr(f"{prefix}/onnxruntime", b"Mach-O fixture")
                archive.writestr(f"{prefix}/Headers/onnxruntime_c_api.h", "#define ORT_API_VERSION 22\n")
            archive.writestr("onnxruntime.xcframework/Info.plist", plistlib.dumps({"AvailableLibraries": libraries}))
            if bad_path:
                archive.writestr("onnxruntime.xcframework/ios-arm64/../../escape", "bad")
        with zipfile.ZipFile(self.package, "w") as archive:
            archive.writestr("runtimes/ios/native/onnxruntime.xcframework.zip", content.getvalue())
            archive.writestr("LICENSE", "MIT\n")
            archive.writestr("Microsoft.ML.OnnxRuntime.nuspec", f"""
                <package xmlns="http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd"><metadata>
                <version>{module.VERSION}</version><repository commit="{commit or module.SOURCE_COMMIT}"/>
                </metadata></package>""")
        digest = base64.b64encode(hashlib.sha512(self.package.read_bytes()).digest()).decode()
        self.digest_patch = patch.object(module, "PACKAGE_SHA512", digest)
        self.digest_patch.start()
        self.addCleanup(self.digest_patch.stop)

    def test_prepares_cloneable_specs_with_verified_local_archives_and_both_slices(self):
        self.package_fixture()
        repo = module.prepare_specs(self.package, self.source, self.root / "prepared")
        clone = self.root / "clone"
        subprocess.run(["git", "clone", "--quiet", repo.as_uri(), str(clone)], check=True)
        for name in ["onnxruntime-c", "onnxruntime-objc"]:
            spec = json.loads((clone / "Specs" / name / module.VERSION / f"{name}.podspec.json").read_text())
            self.assertEqual(module.VERSION, spec["version"])
            archive = self.root / "prepared/archives" / f"{name}-{module.VERSION}.zip"
            self.assertEqual(archive.as_uri(), spec["source"]["http"])
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), spec["source"]["sha256"])
            with zipfile.ZipFile(archive) as contents:
                if name == "onnxruntime-c":
                    self.assertIn("onnxruntime.xcframework/ios-arm64/onnxruntime.framework/onnxruntime", contents.namelist())
                    self.assertIn("onnxruntime.xcframework/ios-arm64_x86_64-simulator/onnxruntime.framework/onnxruntime", contents.namelist())
                    self.assertIn("Headers/onnxruntime_c_api.h", contents.namelist())
                else:
                    self.assertEqual(b"// Objective-C source\n", contents.read("objectivec/ort_env.mm"))

    def test_rejects_a_corrupted_nuget_package(self):
        self.package_fixture()
        with self.package.open("ab") as stream:
            stream.write(b"corrupt")
        with self.assertRaisesRegex(ValueError, "SHA512 mismatch"):
            module.prepare_specs(self.package, self.source, self.root / "prepared")

    def test_rejects_a_different_source_commit_in_the_nuget_metadata(self):
        self.package_fixture(commit="0" * 40)
        with self.assertRaisesRegex(ValueError, "source commit mismatch"):
            module.verify_package(self.package)

    def test_rejects_modified_objective_c_sources(self):
        self.package_fixture()
        (self.source / "objectivec/ort_env.mm").write_text("changed")
        with self.assertRaisesRegex(ValueError, "pristine"):
            module.prepare_specs(self.package, self.source, self.root / "prepared")

    def test_rejects_missing_simulator_framework(self):
        self.package_fixture(missing_simulator=True)
        with self.assertRaisesRegex(ValueError, "device and simulator"):
            module.prepare_specs(self.package, self.source, self.root / "prepared")

    def test_rejects_paths_outside_the_framework(self):
        self.package_fixture(bad_path=True)
        with self.assertRaisesRegex(ValueError, "Invalid path"):
            module.prepare_specs(self.package, self.source, self.root / "prepared")
        self.assertFalse((self.root / "prepared/escape").exists())


if __name__ == "__main__":
    unittest.main()
