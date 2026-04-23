from __future__ import annotations

import hashlib
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

from maya_cython_compile.cli import build_parser, main, normalize_argv
from maya_cython_compile.errors import USAGE_ERROR
from maya_cython_compile.pipeline import ARTIFACT_MANIFEST_FILENAME
from maya_cython_compile.target_builder import ARTIFACT_METADATA_FILENAME
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
                "python_version": "3.11",
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
                        "python_version": "3.11",
                    },
                    "linux-2024": {
                        "platform": "linux",
                        "module_name": "MayaToolLinux",
                        "maya_version": "2024",
                        "python_version": "3.11",
                    },
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def write_fake_wheel(
    repo_root: Path,
    *,
    target_name: str = "default",
    artifact_target_name: str | None = None,
    platform: str = "windows",
    maya_version: str = "2025",
    python_version: str = "3.11",
    module_name: str = "MayaTool",
) -> Path:
    dist_dir = repo_root / "dist" / target_name
    dist_dir.mkdir(parents=True, exist_ok=True)
    wheel_path = dist_dir / "maya_tool-0.1.0-py3-none-any.whl"
    package_root = SRC / "maya_tool"
    metadata = {
        "schema_version": 1,
        "target_name": artifact_target_name or target_name,
        "platform": platform,
        "maya_version": maya_version,
        "python_version": python_version,
        "distribution_name": "maya-tool",
        "package_name": "maya_tool",
        "module_name": module_name,
        "version": "0.1.0",
    }

    with zipfile.ZipFile(wheel_path, "w") as archive:
        for name in (
            "__init__.py",
            "bootstrap.py",
            "_cy_logic.py",
            "_resources.py",
            "tool_manifest.json",
        ):
            archive.write(package_root / name, arcname=f"maya_tool/{name}")
        archive.writestr(f"maya_tool-0.1.0.dist-info/{ARTIFACT_METADATA_FILENAME}", json.dumps(metadata))

    (dist_dir / ARTIFACT_MANIFEST_FILENAME).write_text(
        json.dumps(
            {
                "schema_version": 1,
                "wheel": wheel_path.name,
                "sha256": hashlib.sha256(wheel_path.read_bytes()).hexdigest(),
                "build": metadata,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

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
                "--skip-package",
            ]
        )

        self.assertEqual(args.command, "run")
        self.assertTrue(args.ensure_env)
        self.assertTrue(args.skip_smoke)
        self.assertTrue(args.skip_package)
        self.assertEqual(args.target, "linux-2024")
        self.assertEqual(args.maya_py, "C:/Maya/bin/mayapy.exe")

    def test_build_parser_parses_safety_flags(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["build", "--dry-run", "--force"])

        self.assertEqual(args.command, "build")
        self.assertTrue(args.dry_run)
        self.assertTrue(args.force)

    def test_normalize_argv_keeps_global_flags_valid_after_subcommand(self) -> None:
        normalized = normalize_argv(["build", "--json-errors", "--target", "linux-2024", "--dry-run"])

        self.assertEqual(
            normalized,
            ["--json-errors", "--target", "linux-2024", "build", "--dry-run"],
        )

    def test_build_parser_rejects_maya_version_override_for_assemble(self) -> None:
        parser = build_parser()
        stderr = io.StringIO()

        with redirect_stderr(stderr), self.assertRaises(SystemExit) as exc:
            parser.parse_args(["assemble", "--maya-version", "2024"])

        self.assertEqual(exc.exception.code, 2)
        self.assertIn("--maya-version", stderr.getvalue())

    def test_build_parser_rejects_module_name_override_for_assemble(self) -> None:
        parser = build_parser()
        stderr = io.StringIO()

        with redirect_stderr(stderr), self.assertRaises(SystemExit) as exc:
            parser.parse_args(["assemble", "--module-name", "StudioTool"])

        self.assertEqual(exc.exception.code, 2)
        self.assertIn("--module-name", stderr.getvalue())

    def test_build_parser_rejects_module_name_override_for_run(self) -> None:
        parser = build_parser()
        stderr = io.StringIO()

        with redirect_stderr(stderr), self.assertRaises(SystemExit) as exc:
            parser.parse_args(["run", "--module-name", "StudioTool"])

        self.assertEqual(exc.exception.code, 2)
        self.assertIn("--module-name", stderr.getvalue())

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
        self.assertEqual(payload["config"]["python_version"], "3.11")
        self.assertEqual(payload["config"]["package_name"], "maya_tool")
        self.assertEqual(payload["config"]["module_name"], "MayaToolLinux")

    def test_main_smoke_json_with_fake_wheel(self) -> None:
        repo_root = make_temp_repo("cli-smoke")
        write_multi_target_build_config(repo_root)
        write_fake_wheel(
            repo_root,
            target_name="linux-2024",
            platform="linux",
            maya_version="2024",
            python_version="3.11",
            module_name="MayaToolLinux",
        )
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
        env_path = repo_root / ".conda" / "windows-2025"
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
        self.assertEqual(payload["python_version"], "3.11")
        self.assertEqual(
            payload["environment_file"],
            str(repo_root / "build" / "tmp" / "windows-2025" / "conda-environment.yml"),
        )

    def test_main_run_dry_run_json_previews_full_workflow_when_ensure_env_is_set(self) -> None:
        repo_root = make_temp_repo("cli-run-dry-run-ensure-env")
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
                    "--conda-exe",
                    sys.executable,
                    "--maya-py",
                    str(mayapy),
                    "run",
                    "--json",
                    "--dry-run",
                    "--ensure-env",
                ]
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["dry_run"])
        self.assertEqual(
            list(payload["steps"]),
            ["create_env", "build", "smoke", "assemble", "package"],
        )
        self.assertEqual(payload["steps"]["create_env"]["target"], "linux-2024")
        self.assertEqual(payload["steps"]["build"]["target"], "linux-2024")
        self.assertEqual(payload["steps"]["smoke"]["wheel"], "after build step")
        self.assertEqual(payload["steps"]["assemble"]["wheel"], "after build step")
        self.assertEqual(payload["steps"]["package"]["module_root"], "after assemble step")

    def test_main_package_json_with_existing_module_root(self) -> None:
        repo_root = make_temp_repo("cli-package")
        write_multi_target_build_config(repo_root)
        module_root = repo_root / "dist" / "module" / "linux-2024" / "MayaToolLinux"
        package_root = module_root / "contents" / "scripts" / "maya_tool"
        package_root.mkdir(parents=True, exist_ok=True)
        (package_root / "__init__.py").write_text("", encoding="utf-8")
        (package_root / "bootstrap.py").write_text("def show_ui():\n    return 'ok'\n", encoding="utf-8")
        (module_root / "MayaToolLinux.mod").write_text(
            "+ MAYAVERSION:2024 PLATFORM:linux MayaToolLinux 0.1.0 ./contents",
            encoding="utf-8",
        )
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = main(
                [
                    "--repo-root",
                    str(repo_root),
                    "--target",
                    "linux-2024",
                    "package",
                    "--json",
                ]
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(
            Path(payload["archive"]).name,
            "MayaToolLinux-0.1.0-maya2024-linux.zip",
        )
        self.assertEqual(Path(payload["module_root"]), module_root)

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
        self.assertTrue(payload["checks"]["maya_python_matches_target"])
        self.assertEqual(payload["maya_runtime"]["runtime_platform"], "linux")
        self.assertEqual(payload["maya_runtime"]["target_platform"], "linux")
        self.assertEqual(payload["maya_runtime"]["target_python_version"], "3.11")
        self.assertEqual(payload["maya_runtime"]["library_name"], "python3.11")
        self.assertEqual(payload["maya_runtime"]["library_file"], str(library_file))

    def test_main_json_errors_emits_machine_readable_payload(self) -> None:
        repo_root = make_temp_repo("cli-json-errors")
        write_multi_target_build_config(repo_root)
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            exit_code = main(
                [
                    "--repo-root",
                    str(repo_root),
                    "--json-errors",
                    "--target",
                    "missing-target",
                    "doctor",
                ]
            )

        self.assertEqual(exit_code, USAGE_ERROR)
        payload = json.loads(stderr.getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["command"], "doctor")
        self.assertEqual(payload["target"], "missing-target")
        self.assertEqual(payload["error_code"], "usage_error")
