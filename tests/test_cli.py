from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agents_memory.cli import main  # noqa: E402


class CliTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / ".agents-memory"
        self.project = Path(self.tmp.name) / "project"
        self.project.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_cli(self, *args: str, stdin: str | None = None) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        original_stdin = sys.stdin
        if stdin is not None:
            sys.stdin = io.StringIO(stdin)
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(["--home", str(self.home), *args])
        finally:
            sys.stdin = original_stdin
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def run_cli_with_home(
        self, user_home: Path, *args: str, stdin: str | None = None
    ) -> tuple[int, str, str]:
        original_home = os.environ.get("HOME")
        os.environ["HOME"] = str(user_home)
        try:
            return self.run_cli(*args, stdin=stdin)
        finally:
            if original_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = original_home

    def test_get_initializes_project_without_entries(self) -> None:
        exit_code, output, error = self.run_cli("get", "--cwd", str(self.project))

        self.assertEqual(exit_code, 0, error)
        self.assertIn("Active Project Memory Entries", output)
        self.assertIn("No memory entries found.", output)
        self.assertTrue((self.home / "memory.sqlite").exists())

    def test_get_empty_parent_includes_child_project_entries(self) -> None:
        child_project = self.project / "path-only"
        child_project.mkdir()
        payload = {
            "operations": [
                {
                    "action": "create",
                    "type": "observation",
                    "priority": "medium",
                    "content": "Use the path-only fixture for path identity checks.",
                    "rationale": "The parent workspace is only a container.",
                }
            ]
        }
        exit_code, _, error = self.run_cli(
            "apply",
            "--cwd",
            str(child_project),
            "--agent",
            "codex",
            "--operations-file",
            "-",
            stdin=json.dumps(payload),
        )
        self.assertEqual(exit_code, 0, error)

        exit_code, output, error = self.run_cli("get", "--cwd", str(self.project))

        self.assertEqual(exit_code, 0, error)
        self.assertIn("No memory entries found for the exact project.", output)
        self.assertIn("Related Project Memory Entries", output)
        self.assertIn(f"path:{child_project.resolve()}", output)
        self.assertIn("Use the path-only fixture for path identity checks.", output)

    def test_get_nested_directory_includes_parent_project_entries(self) -> None:
        nested = self.project / "src" / "package"
        nested.mkdir(parents=True)
        payload = {
            "operations": [
                {
                    "action": "create",
                    "type": "instruction",
                    "priority": "high",
                    "content": "Keep memory lookup intuitive from nested directories.",
                    "rationale": "Agents often start below the project root.",
                }
            ]
        }
        exit_code, _, error = self.run_cli(
            "apply",
            "--cwd",
            str(self.project),
            "--agent",
            "codex",
            "--operations-file",
            "-",
            stdin=json.dumps(payload),
        )
        self.assertEqual(exit_code, 0, error)

        exit_code, output, error = self.run_cli("get", "--cwd", str(nested))

        self.assertEqual(exit_code, 0, error)
        self.assertIn("No memory entries found for the exact project.", output)
        self.assertIn("Related Project Memory Entries", output)
        self.assertIn(f"path:{self.project.resolve()}", output)
        self.assertIn("Keep memory lookup intuitive from nested directories.", output)

    def test_create_and_startup_compact_view(self) -> None:
        payload = {
            "operations": [
                {
                    "action": "create",
                    "type": "decision",
                    "priority": "high",
                    "content": "Store project memories outside project directories.",
                    "rationale": "Project directories must not receive generated memory files.",
                }
            ]
        }

        exit_code, _, error = self.run_cli(
            "apply",
            "--cwd",
            str(self.project),
            "--agent",
            "codex",
            "--operations-file",
            "-",
            stdin=json.dumps(payload),
        )
        self.assertEqual(exit_code, 0, error)

        exit_code, output, error = self.run_cli(
            "startup",
            "--cwd",
            str(self.project),
            "--budget-chars",
            "9000",
        )

        self.assertEqual(exit_code, 0, error)
        self.assertIn("Project Memory", output)
        self.assertIn("Active Decisions", output)
        self.assertIn("Store project memories outside project directories.", output)

    def test_update_revises_entry_in_place(self) -> None:
        create_payload = {
            "operations": [
                {
                    "action": "create",
                    "type": "decision",
                    "priority": "medium",
                    "content": "Use an enabled flag for memory injection.",
                    "rationale": "Only current knowledge should be injected.",
                }
            ]
        }
        self.run_cli(
            "apply",
            "--cwd",
            str(self.project),
            "--agent",
            "codex",
            "--operations-file",
            "-",
            stdin=json.dumps(create_payload),
        )

        update_payload = {
            "operations": [
                {
                    "action": "update",
                    "target_id": 1,
                    "type": "decision",
                    "priority": "high",
                    "content": "Use active and archived memory states.",
                    "rationale": "A single active version per idea keeps startup clean.",
                }
            ]
        }
        exit_code, _, error = self.run_cli(
            "apply",
            "--cwd",
            str(self.project),
            "--agent",
            "codex",
            "--operations-file",
            "-",
            stdin=json.dumps(update_payload),
        )
        self.assertEqual(exit_code, 0, error)

        exit_code, all_output, error = self.run_cli("get", "--cwd", str(self.project), "--all")
        self.assertEqual(exit_code, 0, error)
        self.assertIn("Use active and archived memory states.", all_output)
        self.assertNotIn("Use an enabled flag for memory injection.", all_output)

        exit_code, startup_output, error = self.run_cli("startup", "--cwd", str(self.project))
        self.assertEqual(exit_code, 0, error)
        self.assertIn("Use active and archived memory states.", startup_output)

    def test_invalid_budget_fails(self) -> None:
        exit_code, _, error = self.run_cli(
            "startup",
            "--cwd",
            str(self.project),
            "--budget-chars",
            "0",
        )

        self.assertEqual(exit_code, 1)
        self.assertIn("--budget-chars must be greater than zero", error)

    def test_invalid_operation_rolls_back(self) -> None:
        payload = {
            "operations": [
                {
                    "action": "create",
                    "type": "decision",
                    "priority": "high",
                    "content": "This should not persist.",
                    "rationale": "The batch should roll back when a later operation fails.",
                },
                {
                    "action": "archive",
                    "target_id": 999,
                },
            ]
        }

        exit_code, _, error = self.run_cli(
            "apply",
            "--cwd",
            str(self.project),
            "--agent",
            "codex",
            "--operations-file",
            "-",
            stdin=json.dumps(payload),
        )
        self.assertEqual(exit_code, 1)
        self.assertIn("active memory entry #999 was not found", error)

        exit_code, output, error = self.run_cli("get", "--cwd", str(self.project), "--all")
        self.assertEqual(exit_code, 0, error)
        self.assertNotIn("This should not persist.", output)

    def test_cannot_archive_already_archived_entry(self) -> None:
        create_payload = {
            "operations": [
                {
                    "action": "create",
                    "type": "decision",
                    "priority": "medium",
                    "content": "Old decision.",
                    "rationale": "Initial project understanding.",
                }
            ]
        }
        self.run_cli(
            "apply",
            "--cwd",
            str(self.project),
            "--agent",
            "codex",
            "--operations-file",
            "-",
            stdin=json.dumps(create_payload),
        )

        archive_payload = {"operations": [{"action": "archive", "target_id": 1}]}
        exit_code, _, error = self.run_cli(
            "apply",
            "--cwd",
            str(self.project),
            "--agent",
            "codex",
            "--operations-file",
            "-",
            stdin=json.dumps(archive_payload),
        )
        self.assertEqual(exit_code, 0, error)

        exit_code, _, error = self.run_cli(
            "apply",
            "--cwd",
            str(self.project),
            "--agent",
            "codex",
            "--operations-file",
            "-",
            stdin=json.dumps(archive_payload),
        )
        self.assertEqual(exit_code, 1)
        self.assertIn("active memory entry #1 was not found", error)

        exit_code, output, error = self.run_cli("startup", "--cwd", str(self.project))
        self.assertEqual(exit_code, 0, error)
        self.assertNotIn("Old decision.", output)

    def test_hook_returns_codex_payload(self) -> None:
        payload = {
            "operations": [
                {
                    "action": "create",
                    "type": "instruction",
                    "priority": "high",
                    "content": "Keep startup context compact.",
                    "rationale": "Agents should not waste context on noise.",
                }
            ]
        }
        self.run_cli(
            "apply",
            "--cwd",
            str(self.project),
            "--agent",
            "codex",
            "--operations-file",
            "-",
            stdin=json.dumps(payload),
        )

        exit_code, output, error = self.run_cli(
            "hook", "--cwd", str(self.project), "--agent", "codex", "--format", "json"
        )
        self.assertEqual(exit_code, 0, error)
        data = json.loads(output)
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "SessionStart")
        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Keep startup context compact.", context)
        self.assertNotIn("suppressOutput", data["hookSpecificOutput"])

    def test_setup_configures_codex_claude_and_opencode(self) -> None:
        user_home = Path(self.tmp.name)
        (user_home / ".codex").mkdir()
        (user_home / ".claude").mkdir()
        (user_home / ".config" / "opencode").mkdir(parents=True)
        shutil.copytree(ROOT / "skills", self.home / "skills")
        plugin_source = self.home / "plugins" / "opencode"
        plugin_source.mkdir(parents=True)
        plugin_js = "export const AgentsMemoryPlugin = async () => ({})\n"
        (plugin_source / "agents-memory.js").write_text(plugin_js, encoding="utf-8")

        exit_code, _, error = self.run_cli_with_home(
            user_home, "setup", "--agent", "codex", "--cwd", str(self.project)
        )
        self.assertEqual(exit_code, 0, error)
        codex_hooks_path = user_home / ".codex" / "hooks.json"
        codex_hooks = json.loads(codex_hooks_path.read_text(encoding="utf-8"))
        self.assertIn("SessionStart", codex_hooks["hooks"])

        exit_code, _, error = self.run_cli_with_home(
            user_home, "setup", "--agent", "claude", "--cwd", str(self.project)
        )
        self.assertEqual(exit_code, 0, error)
        claude_settings_path = user_home / ".claude" / "settings.json"
        claude_settings = json.loads(claude_settings_path.read_text(encoding="utf-8"))
        self.assertIn("SessionStart", claude_settings["hooks"])

        exit_code, _, error = self.run_cli_with_home(
            user_home, "setup", "--agent", "opencode", "--cwd", str(self.project)
        )
        self.assertEqual(exit_code, 0, error)
        plugin_link = user_home / ".config" / "opencode" / "plugins" / "agents-memory.js"
        self.assertTrue(plugin_link.is_symlink())

    def test_setup_enables_codex_hook_after_user_trust(self) -> None:
        user_home = Path(self.tmp.name)
        codex_dir = user_home / ".codex"
        codex_dir.mkdir()
        shutil.copytree(ROOT / "skills", self.home / "skills")
        state_key = f"{codex_dir / 'hooks.json'}:session_start:0:0"
        (codex_dir / "config.toml").write_text(
            "\n".join(
                [
                    "[features]",
                    "hooks = true",
                    "",
                    "[hooks.state]",
                    "",
                    f'[hooks.state."{state_key}"]',
                    "enabled = false",
                    'trusted_hash = "sha256:already-reviewed"',
                    "",
                ]
            ),
            encoding="utf-8",
        )

        exit_code, _, error = self.run_cli_with_home(
            user_home, "setup", "--agent", "codex", "--cwd", str(self.project)
        )

        self.assertEqual(exit_code, 0, error)
        config = (codex_dir / "config.toml").read_text(encoding="utf-8")
        self.assertIn(f'[hooks.state."{state_key}"]', config)
        self.assertIn("enabled = true", config)

    def test_doctor_reports_codex_hook_state(self) -> None:
        user_home = Path(self.tmp.name)
        codex_dir = user_home / ".codex"
        codex_dir.mkdir()
        shutil.copytree(ROOT / "skills", self.home / "skills")

        exit_code, _, error = self.run_cli_with_home(
            user_home, "setup", "--agent", "codex", "--cwd", str(self.project)
        )
        self.assertEqual(exit_code, 0, error)

        exit_code, output, error = self.run_cli_with_home(user_home, "doctor")

        self.assertEqual(exit_code, 0, error)
        self.assertIn("Codex SessionStart hook: installed", output)
        self.assertIn("trusted=false", output)

    def test_setup_claude_replaces_legacy_hook_without_duplicating(self) -> None:
        user_home = Path(self.tmp.name)
        claude_dir = user_home / ".claude"
        claude_dir.mkdir()
        shutil.copytree(ROOT / "skills", self.home / "skills")
        legacy = (
            f"{self.home / 'bin' / 'agents-memory'} hook --agent claude-code "
            '--cwd "${CLAUDE_PROJECT_DIR:-$PWD}" --format text'
        )
        (claude_dir / "settings.json").write_text(
            json.dumps(
                {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": legacy}]}]}}
            ),
            encoding="utf-8",
        )

        exit_code, _, error = self.run_cli_with_home(
            user_home, "setup", "--agent", "claude", "--cwd", str(self.project)
        )
        self.assertEqual(exit_code, 0, error)

        settings = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
        commands = [
            hook["command"]
            for group in settings["hooks"]["SessionStart"]
            for hook in group["hooks"]
            if "agents-memory" in hook["command"]
        ]
        self.assertEqual(len(commands), 1)
        self.assertIn("--agent claude ", commands[0] + " ")
        self.assertNotIn("claude-code", commands[0])

    def test_doctor_reports_all_three_agents(self) -> None:
        user_home = Path(self.tmp.name)
        (user_home / ".claude").mkdir()
        shutil.copytree(ROOT / "skills", self.home / "skills")
        self.run_cli_with_home(user_home, "setup", "--agent", "claude", "--cwd", str(self.project))

        exit_code, output, error = self.run_cli_with_home(user_home, "doctor")

        self.assertEqual(exit_code, 0, error)
        self.assertIn("Claude SessionStart hook: installed", output)
        self.assertIn("Codex", output)
        self.assertIn("OpenCode", output)

    def test_get_groups_same_type_entries_under_single_header(self) -> None:
        payload = {
            "operations": [
                {
                    "action": "create",
                    "type": "instruction",
                    "priority": "high",
                    "content": "First high-priority instruction.",
                    "rationale": "Critical workflow step.",
                },
                {
                    "action": "create",
                    "type": "decision",
                    "priority": "high",
                    "content": "A high-priority decision.",
                    "rationale": "Architecture choice.",
                },
                {
                    "action": "create",
                    "type": "instruction",
                    "priority": "medium",
                    "content": "Second medium-priority instruction.",
                    "rationale": "Helpful but not critical.",
                },
            ]
        }
        exit_code, _, error = self.run_cli(
            "apply",
            "--cwd",
            str(self.project),
            "--agent",
            "claude",
            "--operations-file",
            "-",
            stdin=json.dumps(payload),
        )
        self.assertEqual(exit_code, 0, error)

        exit_code, output, error = self.run_cli("get", "--cwd", str(self.project))
        self.assertEqual(exit_code, 0, error)

        first_header = output.find("Active Instructions")
        self.assertGreater(first_header, -1, "Expected 'Active Instructions' section")
        second_header = output.find("Active Instructions", first_header + 1)
        self.assertEqual(
            second_header,
            -1,
            "Found duplicate 'Active Instructions' header — grouping is broken",
        )
        self.assertIn("First high-priority instruction.", output)
        self.assertIn("Second medium-priority instruction.", output)
        self.assertIn("A high-priority decision.", output)

    def test_dashboard_help_lists_flags(self) -> None:
        out = io.StringIO()
        with self.assertRaises(SystemExit) as ctx, redirect_stdout(out):
            main(["--home", str(self.home), "dashboard", "--help"])
        self.assertEqual(ctx.exception.code, 0)
        text = out.getvalue()
        self.assertIn("--port", text)
        self.assertNotIn("--host", text)

    def test_dashboard_invokes_run_dashboard(self) -> None:
        with patch("agents_memory.cli.run_dashboard") as mock_run:
            exit_code, _, error = self.run_cli("dashboard")
        self.assertEqual(exit_code, 0, error)
        mock_run.assert_called_once()
        self.assertEqual(mock_run.call_args.args[0], self.home)
        self.assertEqual(mock_run.call_args.kwargs["port"], 0)


if __name__ == "__main__":
    unittest.main()
