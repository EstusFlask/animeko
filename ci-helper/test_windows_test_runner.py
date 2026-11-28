import os
import subprocess
import tempfile
import unittest
from pathlib import Path


RUNNER_SCRIPT = Path(__file__).with_name("verify") / "run-ani-test-windows-x64.ps1"


@unittest.skipUnless(os.name == "nt", "requires Windows PowerShell and Start-Process")
class WindowsTestRunnerTest(unittest.TestCase):
    def test_reports_child_logs_and_preserves_its_exit_code(self):
        with tempfile.TemporaryDirectory(prefix="ani-verify-runner-") as directory:
            root = Path(directory)
            environment = dict(os.environ, ANI_FAKE_EXE=str(root / "Ani.exe"))
            compile_result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", r"""
Add-Type -OutputAssembly $env:ANI_FAKE_EXE -OutputType ConsoleApplication -TypeDefinition @'
using System;
using System.IO;
public class VerificationFixture {
    public static int Main() {
        string task = Environment.GetEnvironmentVariable("ANIMEKO_DESKTOP_TEST_TASK");
        string root = Environment.GetEnvironmentVariable("ANIMEKO_DESKTOP_TEST_DATA_DIR");
        if (!String.IsNullOrEmpty(root)) {
            string logs = Path.Combine(root, "data", "logs");
            Directory.CreateDirectory(logs);
            File.WriteAllText(Path.Combine(logs, "app.log"), "Windows native input verification: fixture diagnostic");
        }
        Console.WriteLine("fixture stdout");
        Console.Error.WriteLine("fixture stderr");
        return task == "success" ? 0 : 7;
    }
}
'@
"""],
                env=environment, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(0, compile_result.returncode, compile_result.stderr)
            for task, exit_code in (("success", 0), ("failure", 7)):
                with self.subTest(task=task):
                    result = subprocess.run(
                        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                         "-File", str(RUNNER_SCRIPT.resolve()), str(root), task],
                        cwd=root, capture_output=True, text=True, timeout=30,
                    )
                    self.assertEqual(exit_code, result.returncode, result.stdout + result.stderr)
                    self.assertIn("fixture diagnostic", result.stdout)
                    diagnostics = root / "update-e2e" / f"windows-verify-{task}"
                    self.assertIn("fixture stdout", (diagnostics / "stdout.log").read_text())
                    self.assertIn("fixture stderr", (diagnostics / "stderr.log").read_text())


if __name__ == "__main__":
    unittest.main()
