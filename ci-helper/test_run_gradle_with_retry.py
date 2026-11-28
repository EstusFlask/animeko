import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch


spec = importlib.util.spec_from_file_location("gradle_retry", Path(__file__).with_name("run-gradle-with-retry.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GradleDependencyRetryTest(unittest.TestCase):
    def setUp(self):
        output = patch("sys.stdout", new_callable=io.StringIO)
        self.output = output.start()
        self.addCleanup(output.stop)

    def test_rate_limit_waits_then_retries_the_same_command(self):
        run = Mock(side_effect=[(1, True), (1, True), (0, False)])
        sleep = Mock()
        status = module.run_gradle(["--stacktrace", "-Dorg.gradle.jvmargs=-Xmx4g -Dfile.encoding=UTF-8"], run=run, sleep=sleep)
        self.assertEqual(0, status)
        self.assertEqual([30, 60], [call.args[0] for call in sleep.call_args_list])
        self.assertEqual(3, run.call_count)
        self.assertEqual(run.call_args_list[0], run.call_args_list[2])
        self.assertIn("-Dorg.gradle.jvmargs=-Xmx4g -Dfile.encoding=UTF-8", run.call_args.args[0])

    def test_rate_limit_exhaustion_preserves_the_failure(self):
        run = Mock(return_value=(7, True))
        sleep = Mock()
        self.assertEqual(7, module.run_gradle([], run=run, sleep=sleep))
        self.assertEqual(3, run.call_count)
        self.assertEqual(2, sleep.call_count)

    def test_compiler_or_test_failures_are_not_retried(self):
        run = Mock(return_value=(1, False))
        sleep = Mock()
        self.assertEqual(1, module.run_gradle([], run=run, sleep=sleep))
        run.assert_called_once()
        sleep.assert_not_called()

    def test_actual_process_output_detects_maven_rate_limit(self):
        status, limited = module.run_once(
            [sys.executable, "-c", "import sys; print('Received status code 429 from server: Too Many Requests'); sys.exit(4)"],
            module.ROOT,
        )
        self.assertEqual((4, True), (status, limited))
        self.assertIn("Received status code 429", self.output.getvalue())

    def test_actual_process_output_preserves_other_errors(self):
        status, limited = module.run_once(
            [sys.executable, "-c", "import sys; print('Compilation error'); sys.exit(2)"], module.ROOT,
        )
        self.assertEqual((2, False), (status, limited))


if __name__ == "__main__":
    unittest.main()
