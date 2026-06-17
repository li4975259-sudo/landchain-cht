import unittest
from pathlib import Path

from app.config import Settings
from app.services.shell_executor import ShellExecutor


class ShellExecutorTests(unittest.TestCase):
    def _settings(self) -> Settings:
        return Settings(
            agent_shell_enabled=True,
            agent_shell_mode="allowlist",
            agent_shell_allowlist=r"^python -c ",
            agent_shell_cwd=Path("./storage/test-shell"),
            agent_shell_timeout=5,
        )

    def test_execute_runs_safe_command(self) -> None:
        executor = ShellExecutor(self._settings())
        result = executor.execute('python -c "print(123)"')
        self.assertTrue(result["success"])
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("123", result["stdout"])

    def test_execute_blocks_shell_operators(self) -> None:
        executor = ShellExecutor(self._settings())
        with self.assertRaises(ValueError):
            executor.execute('python -c "print(1)" && python -c "print(2)"')


if __name__ == "__main__":
    unittest.main()
