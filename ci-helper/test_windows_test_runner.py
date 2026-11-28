import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


RUNNER_SCRIPT = Path(__file__).with_name("verify") / "run-ani-test-windows-x64.ps1"


@unittest.skipUnless(os.name == "nt", "requires Windows PowerShell and Start-Process")
class WindowsTestRunnerTest(unittest.TestCase):
    def test_reports_child_logs_and_preserves_its_exit_code(self):
        with tempfile.TemporaryDirectory(prefix="ani-verify-runner-") as directory:
            root = Path(directory)
            python_directory = Path(sys.base_prefix)
            shutil.copyfile(python_directory / "python.exe", root / "Ani.exe")
            fixture_directory = root / "fixture"
            fixture_directory.mkdir()
            # The installed interpreter launches a real child executable with no compiler dependency.
            (fixture_directory / "sitecustomize.py").write_text(
                textwrap.dedent("""
                    import os
                    import sys
                    from pathlib import Path

                    logs = Path(os.environ["ANIMEKO_DESKTOP_TEST_DATA_DIR"]) / "data" / "logs"
                    logs.mkdir(parents=True, exist_ok=True)
                    (logs / "app.log").write_text("Windows native input verification: fixture diagnostic")
                    print("fixture stdout", flush=True)
                    print("fixture stderr", file=sys.stderr, flush=True)
                    os._exit(0 if os.environ["ANIMEKO_DESKTOP_TEST_TASK"] == "success" else 7)
                """),
                encoding="utf-8",
            )
            environment = dict(
                os.environ,
                PYTHONHOME=str(python_directory),
                PYTHONPATH=str(fixture_directory),
                PATH=os.pathsep.join((str(python_directory), os.environ["PATH"])),
            )
            for task, exit_code in (("success", 0), ("failure", 7)):
                with self.subTest(task=task):
                    result = subprocess.run(
                        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                         "-File", str(RUNNER_SCRIPT.resolve()), str(root), task],
                        cwd=root, env=environment, capture_output=True, text=True, timeout=120,
                    )
                    self.assertEqual(exit_code, result.returncode, result.stdout + result.stderr)
                    self.assertIn("fixture diagnostic", result.stdout)
                    diagnostics = root / "update-e2e" / f"windows-verify-{task}"
                    self.assertIn("fixture stdout", (diagnostics / "stdout.log").read_text())
                    self.assertIn("fixture stderr", (diagnostics / "stderr.log").read_text())


if __name__ == "__main__":
    unittest.main()
