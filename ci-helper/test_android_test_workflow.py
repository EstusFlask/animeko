import re
import unittest
from pathlib import Path

import yaml


class AndroidTestWorkflowTest(unittest.TestCase):
    def test_hosted_ubuntu_build_leaves_memory_for_android_packaging(self):
        workflows = Path(__file__).resolve().parents[1] / ".github" / "workflows"
        for name in ("build.yml", "release.yml"):
            workflow = yaml.safe_load((workflows / name).read_text(encoding="utf-8"))
            for job in workflow["jobs"].values():
                if not job.get("name", "").startswith("Build (") or job.get("runs-on") != ["ubuntu-24.04"]:
                    continue
                commands = [step.get("run", "") for step in job["steps"]]
                builds = [cmd for cmd in commands if "./gradlew " in cmd]
                self.assertTrue(builds)
                for command in builds:
                    with self.subTest(workflow=name, command=command.split('"')[0]):
                        heaps = re.findall(r"-Xmx(\d+)g", command)
                        self.assertGreaterEqual(len(heaps), 2)
                        self.assertLessEqual(sum(map(int, heaps[:2])), 8)
                        self.assertIn("--max-workers=2", command)

    def test_hosted_device_jobs_reserve_memory_and_build_the_emulator_abi(self):
        workflows = Path(__file__).resolve().parents[1] / ".github" / "workflows"
        for name in ("build.yml", "release.yml"):
            workflow = yaml.safe_load((workflows / name).read_text(encoding="utf-8"))
            jobs = [
                job for job in workflow["jobs"].values()
                if job.get("name", "").startswith("Android Instrumented Test (")
                and job.get("runs-on") == ["ubuntu-24.04"]
            ]
            if name == "build.yml":
                self.assertEqual(2, len(jobs), name)
            for job in jobs:
                with self.subTest(workflow=name, job=job["name"]):
                    commands = [step.get("run", "") for step in job["steps"]]
                    self.assertTrue(any("ani.android.abis=x86_64" in cmd for cmd in commands))
                    builds = [cmd for cmd in commands if "assembleAndroidDeviceTest" in cmd]
                    self.assertTrue(builds)
                    for command in builds:
                        heaps = re.findall(r"-Xmx(\d+)g", command)
                        self.assertGreaterEqual(len(heaps), 2)
                        self.assertLessEqual(sum(map(int, heaps[:2])), 8)
                        self.assertIn("--max-workers=2", command)


if __name__ == "__main__":
    unittest.main()
