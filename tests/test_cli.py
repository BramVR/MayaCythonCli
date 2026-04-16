from __future__ import annotations

import io
import json
import shutil
import sys
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TMP_ROOT = ROOT / "build" / "test-tmp"
PROJECT_VERSION = "0.1.0"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from maya_cython_compile.cli import build_parser, main
from maya_cython_compile.errors import USAGE_ERROR


def write_build_config(repo_root: Path) -> None:
    (repo_root / "build-config.json").write_text(
        json.dumps(
            {
                "distribution_name": "maya-tool",
                "package_name": "maya_tool",
                "package_dir": "src/maya_tool",
                "module_name": "MayaTool",
                "maya_version": "2025",
                "version": "0.1.0",
                "compiled_modules": ["_cy_logic"],
                "package_data": ["*.json"],
                "smoke": {
                    "callable": "show_ui",
                    "compiled_modules": ["_cy_logic"],
                    "resource_check": "tool_manifest.json",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def make_temp_repo(name: str) -> Path:
    repo_root = TMP_ROOT / name
    if repo_root.exists():
        shutil.rmtree(repo_root)
    repo_root.mkdir(parents=True, exist_ok=True)
    return repo_root


def write_fake_wheel(repo_root: Path) -> Path:
    dist_dir = repo_root / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    wheel_path = dist_dir / "maya_tool-0.1.0-py3-none-any.whl"
    package_root = SRC / "maya_tool"

    with zipfile.ZipFile(wheel_path, "w") as archive:
        for name in (
            "__init__.py",
            "bootstrap.py",
            "_cy_logic.py",
            "_resources.py",
            "tool_manifest.json",
        ):
            archive.write(package_root / name, arcname=f"maya_tool/{name}")

    return wheel_path


def write_fake_maya_runtime(repo_root: Path) -> Path:
    maya_root = repo_root / "fake-maya"
    mayapy = maya_root / "bin" / "mayapy.exe"
    mayapy.parent.mkdir(parents=True, exist_ok=True)
    mayapy.write_text("", encoding="utf-8")
    (maya_root / "Python" / "Include").mkdir(parents=True, exist_ok=True)
    lib_dir = maya_root / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)
    (lib_dir / "python311.lib").write_text("", encoding="utf-8")
    return mayapy


class CliTests(unittest.TestCase):
    def test_build_parser_version_flag(self) -> None:
        parser = build_parser()
        stdout = io.StringIO()

        with redirect_stdout(stdout), self.assertRaises(SystemExit) as exc:
            parser.parse_args(["--version"])

        self.assertEqual(exc.exception.code, 0)
        self.assertEqual(stdout.getvalue().strip(), f"maya-cython-compile {PROJECT_VERSION}")

    def test_build_parser_parses_run_command(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "--repo-root",
                "C:/repo",
                "--maya-py",
                "C:/Maya/bin/mayapy.exe",
                "run",
                "--ensure-env",
                "--skip-smoke",
            ]
        )

        self.assertEqual(args.command, "run")
        self.assertTrue(args.ensure_env)
        self.assertTrue(args.skip_smoke)
        self.assertEqual(args.maya_py, "C:/Maya/bin/mayapy.exe")

    def test_build_parser_parses_safety_flags(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["build", "--dry-run", "--force"])

        self.assertEqual(args.command, "build")
        self.assertTrue(args.dry_run)
        self.assertTrue(args.force)

    def test_main_config_show_json(self) -> None:
        repo_root = make_temp_repo("cli-config-show")
        write_build_config(repo_root)
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(["--repo-root", str(repo_root), "config", "show", "--json"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["config"]["package_name"], "maya_tool")
        self.assertEqual(payload["config"]["module_name"], "MayaTool")

    def test_main_smoke_json_with_fake_wheel(self) -> None:
        repo_root = make_temp_repo("cli-smoke")
        write_build_config(repo_root)
        write_fake_wheel(repo_root)
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = main(
                [
                    "--repo-root",
                    str(repo_root),
                    "smoke",
                    "--json",
                    "--maya-py",
                    sys.executable,
                ]
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(Path(payload["wheel"]).name, "maya_tool-0.1.0-py3-none-any.whl")
        self.assertEqual(payload["smoke_output"], ["placeholder_ns_tool", "True"])

    def test_main_create_env_dry_run_json_shows_refresh(self) -> None:
        repo_root = make_temp_repo("cli-create-env-dry-run")
        write_build_config(repo_root)
        env_path = repo_root / ".conda" / "maya-cython-build"
        env_path.mkdir(parents=True, exist_ok=True)
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = main(
                [
                    "--repo-root",
                    str(repo_root),
                    "--conda-exe",
                    sys.executable,
                    "create-env",
                    "--json",
                    "--dry-run",
                ]
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["command"], "create-env")
        self.assertIn("--force", payload["would_run"])
        self.assertEqual(payload["delete"][0]["path"], str(env_path))

    def test_main_build_dry_run_json_lists_cleanup_targets(self) -> None:
        repo_root = make_temp_repo("cli-build-dry-run")
        write_build_config(repo_root)
        env_path = repo_root / ".conda" / "maya-cython-build"
        env_path.mkdir(parents=True, exist_ok=True)
        mayapy = write_fake_maya_runtime(repo_root)
        (repo_root / "build" / "target-build").mkdir(parents=True, exist_ok=True)
        (repo_root / "build" / "tmp").mkdir(parents=True, exist_ok=True)
        (repo_root / "maya_tool.egg-info").mkdir(parents=True, exist_ok=True)
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = main(
                [
                    "--repo-root",
                    str(repo_root),
                    "--env-path",
                    str(env_path),
                    "--maya-py",
                    str(mayapy),
                    "build",
                    "--json",
                    "--dry-run",
                ]
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        deleted_paths = {item["path"] for item in payload["delete"]}
        self.assertIn(str(repo_root / "build" / "target-build"), deleted_paths)
        self.assertIn(str(repo_root / "build" / "tmp"), deleted_paths)
        self.assertIn(str(repo_root / "maya_tool.egg-info"), deleted_paths)

    def test_main_build_requires_force_without_prompt_when_cleanup_targets_exist(self) -> None:
        repo_root = make_temp_repo("cli-build-needs-force")
        write_build_config(repo_root)
        env_path = repo_root / ".conda" / "maya-cython-build"
        env_path.mkdir(parents=True, exist_ok=True)
        mayapy = write_fake_maya_runtime(repo_root)
        (repo_root / "build" / "target-build").mkdir(parents=True, exist_ok=True)
        stderr = io.StringIO()

        with redirect_stderr(stderr), mock.patch("builtins.input", side_effect=AssertionError("stdin not allowed")):
            exit_code = main(
                [
                    "--repo-root",
                    str(repo_root),
                    "--env-path",
                    str(env_path),
                    "--maya-py",
                    str(mayapy),
                    "build",
                ]
            )

        self.assertEqual(exit_code, USAGE_ERROR)
        self.assertIn("Run with --dry-run to inspect the plan", stderr.getvalue())
