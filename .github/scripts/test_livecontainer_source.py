import importlib.util
import json
import plistlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True

spec = importlib.util.spec_from_file_location("livecontainer_source", Path(__file__).with_name("livecontainer_source.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LiveContainerSourceTests(unittest.TestCase):
    def version(self, version="4.9.0", build="50410", size=128):
        return {"version": version, "buildVersion": build, "size": size, "downloadURL": "https://github.com/owner/repo/releases/download/v" + version + "/Animeko-" + version + ".ipa", "date": "2026-10-31T00:00:00Z", "minOSVersion": "16.0"}

    def test_source_url_and_identity_are_stable_across_releases(self):
        first = module.build_source("owner/repo", [self.version()])
        newer = module.build_source("owner/repo", [self.version(), self.version("4.10.0", "50411")])
        self.assertEqual(first["sourceURL"], newer["sourceURL"])
        self.assertEqual(first["identifier"], newer["identifier"])
        self.assertEqual("4.10.0", newer["apps"][0]["version"])
        self.assertEqual(2, len(newer["apps"][0]["versions"]))
        self.assertEqual("Animeko", newer["apps"][0]["name"])
        self.assertEqual("org.animeko.animeko", newer["apps"][0]["bundleIdentifier"])

    def test_rebuild_orders_by_numeric_build_number(self):
        source = module.build_source("owner/repo", [self.version(build="9"), self.version(build="10")])
        self.assertEqual("10", source["apps"][0]["buildVersion"])

    def test_prereleases_and_source_release_do_not_enter_feed(self):
        for release in [{"draft": True, "prerelease": False, "tag_name": "v4.9.0"}, {"draft": False, "prerelease": True, "tag_name": "v4.9.0"}, {"draft": False, "prerelease": False, "tag_name": module.SOURCE_TAG}]:
            self.assertIsNone(module.release_version("owner/repo", release, Path("unused")))

    def test_manual_release_can_read_ipa_metadata_without_build_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            ipa = Path(temporary) / "Animeko-4.9.0.ipa"
            with zipfile.ZipFile(ipa, "w") as archive:
                archive.writestr("Payload/Animeko.app/Info.plist", plistlib.dumps({"CFBundleIdentifier": module.BUNDLE_IDENTIFIER, "CFBundleVersion": "50411", "CFBundleShortVersionString": "4.9.0", "MinimumOSVersion": "16.0"}))
            version = module.inspect_ipa(ipa, download_url="https://example.test/Animeko.ipa", date="2026-10-31")
            self.assertEqual("50411", version["buildVersion"])
            self.assertEqual(ipa.stat().st_size, version["size"])

    def test_empty_feed_fails_without_publishing_empty_source(self):
        with self.assertRaises(ValueError):
            module.build_source("owner/repo", [])


if __name__ == "__main__":
    unittest.main()
