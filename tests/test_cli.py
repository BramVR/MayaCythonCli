from __future__ import annotations

import io
import json
import sys
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PROJECT_VERSION = "0.1.0"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from maya_cython_compile.cli import build_parser, main
from maya_cython_compile.errors import USAGE_ERROR
from probe_fixtures import make_probe_completed_process, make_temp_repo, write_fake_maya_probe_layout


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


def write_multi_target_build_config(repo_root: Path) -> None:
    (repo_root / "build-config.json").write_text(
        json.dumps(
            {
                "distribution_name": "maya-tool",
                "package_name": "maya_tool",
                "package_dir": "src/maya_tool",
                "version": "0.1.0",
                "compiled_modules": ["_cy_logic"],
                "package_data": ["*.json"],
                "smoke": {
                    "callable": "show_ui",
                    "compiled_modules": ["_cy_logic"],
                    "resource_check": "tool_manifest.json",
                },
                "default_target": "windows-2025",
                "targets": {
                    "windows-2025": {
                        "platform": "windows",
                        "module_name": "MayaToolWin",
                        "maya_version": "2025",
                    },
                    "linux-2024": {
                        "platform": "linux",
                        "module_name": "MayaToolLinux",
                        "maya_version": "2024",
                    },
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def write_fake_wheel(repo_root: Path, *, target_name: str = "default") -> Path:
    dist_dir = repo_root / "dist" / target_name
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
                "--target",
                "linux-2024",
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
        self.assertEqual(args.target, "linux-2024")
        self.assertEqual(args.maya_py, "C:/Maya/bin/mayapy.exe")

    def test_build_parser_parses_safety_flags(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["build", "--dry-run", "--force"])

        self.assertEqual(args.command, "build")
        self.assertTrue(args.dry_run)
        self.assertTrue(args.force)

    def test_main_config_show_json(self) -> None:
        repo_root = make_temp_repo("cli-config-show")
        write_multi_target_build_config(repo_root)
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(["--repo-root", str(repo_root), "--target", "linux-2024", "config", "show", "--json"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["config"]["target"], "linux-2024")
        self.assertEqual(payload["config"]["platform"], "linux")
        self.assertEqual(payload["config"]["package_name"], "maya_tool")
        self.assertEqual(payload["config"]["module_name"], "MayaToolLinux")

    def test_main_smoke_json_with_fake_wheel(self) -> None:
        repo_root = make_temp_repo("cli-smoke")
        write_multi_target_build_config(repo_root)
        write_fake_wheel(repo_root, target_name="linux-2024")
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = main(
                [
                    "--repo-root",
                    str(repo_root),
                    "--target",
                    "linux-2024",
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
        write_multi_target_build_config(repo_root)
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
        write_multi_target_build_config(repo_root)
        env_path = repo_root / ".conda" / "maya-cython-build"
        env_path.mkdir(parents=True, exist_ok=True)
        mayapy, include_dir, library_file = write_fake_maya_probe_layout(
            repo_root,
            library_filename="libpython3.11.so",
        )
        (repo_root / "build" / "target-build" / "linux-2024").mkdir(parents=True, exist_ok=True)
        (repo_root / "build" / "tmp" / "linux-2024").mkdir(parents=True, exist_ok=True)
        (repo_root / "dist" / "linux-2024").mkdir(parents=True, exist_ok=True)
        (repo_root / "maya_tool.egg-info").mkdir(parents=True, exist_ok=True)
        stdout = io.StringIO()

        with redirect_stdout(stdout), mock.patch(
            "maya_cython_compile.pipeline.subprocess.run",
            return_value=make_probe_completed_process(
                mayapy=mayapy,
                include_dir=include_dir,
                library_file=library_file,
                runtime_platform="linux",
            ),
        ):
            exit_code = main(
                [
                    "--repo-root",
                    str(repo_root),
                    "--target",
                    "linux-2024",
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
        self.assertEqual(payload["target"], "linux-2024")
        self.assertIn(str(repo_root / "build" / "target-build" / "linux-2024"), deleted_paths)
        self.assertIn(str(repo_root / "build" / "tmp" / "linux-2024"), deleted_paths)
        self.assertIn(str(repo_root / "dist" / "linux-2024"), deleted_paths)
        self.assertIn(str(repo_root / "maya_tool.egg-info"), deleted_paths)

    def test_main_build_requires_force_without_prompt_when_cleanup_targets_exist(self) -> None:
        repo_root = make_temp_repo("cli-build-needs-force")
        write_multi_target_build_config(repo_root)
        env_path = repo_root / ".conda" / "maya-cython-build"
        env_path.mkdir(parents=True, exist_ok=True)
        mayapy, include_dir, library_file = write_fake_maya_probe_layout(
            repo_root,
            library_filename="python311.lib",
        )
        (repo_root / "build" / "target-build" / "windows-2025").mkdir(parents=True, exist_ok=True)
        stderr = io.StringIO()

        with (
            redirect_stderr(stderr),
            mock.patch("builtins.input", side_effect=AssertionError("stdin not allowed")),
            mock.patch(
                "maya_cython_compile.pipeline.subprocess.run",
                return_value=make_probe_completed_process(
                    mayapy=mayapy,
                    include_dir=include_dir,
                    library_file=library_file,
                    runtime_platform="windows",
                ),
            ),
        ):
            exit_code = main(
                [
                    "--repo-root",
                    str(repo_root),
                    "--target",
                    "windows-2025",
                    "--env-path",
                    str(env_path),
                    "--maya-py",
                    str(mayapy),
                    "build",
                ]
            )

        self.assertEqual(exit_code, USAGE_ERROR)
        self.assertIn("Run with --dry-run to inspect the plan", stderr.getvalue())

    def test_main_doctor_json_reports_target_aware_runtime_metadata(self) -> None:
        repo_root = make_temp_repo("cli-doctor-runtime")
        write_multi_target_build_config(repo_root)
        mayapy, include_dir, library_file = write_fake_maya_probe_layout(
            repo_root,
            library_filename="libpython3.11.so",
        )
        stdout = io.StringIO()

        with redirect_stdout(stdout), mock.patch(
            "maya_cython_compile.pipeline.subprocess.run",
            return_value=make_probe_completed_process(
                mayapy=mayapy,
                include_dir=include_dir,
                library_file=library_file,
                runtime_platform="linux",
            ),
        ):
            exit_code = main(
                [
                    "--repo-root",
                    str(repo_root),
                    "--target",
                    "linux-2024",
                    "--maya-py",
                    str(mayapy),
                    "doctor",
                    "--json",
                ]
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["checks"]["maya_probe_ok"])
        self.assertTrue(payload["checks"]["maya_platform_matches_target"])
        self.assertEqual(payload["maya_runtime"]["runtime_platform"], "linux")
        self.assertEqual(payload["maya_runtime"]["target_platform"], "linux")
        self.assertEqual(payload["maya_runtime"]["library_name"], "python3.11")
        self.assertEqual(payload["maya_runtime"]["library_file"], str(library_file))
