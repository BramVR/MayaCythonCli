from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from maya_cython_compile.config import resolve_config
from maya_cython_compile.errors import DEPENDENCY_ERROR, CliError
from maya_cython_compile.pipeline import build, ensure_maya_build_runtime, probe_maya_runtime
from probe_fixtures import make_probe_completed_process, make_temp_repo, write_fake_maya_probe_layout


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


class PipelineTests(unittest.TestCase):
    def test_probe_maya_runtime_returns_explicit_linux_metadata(self) -> None:
        repo_root = make_temp_repo("pipeline-probe-linux")
        mayapy, include_dir, library_file = write_fake_maya_probe_layout(
            repo_root,
            library_filename="libpython3.11.so.1.0",
        )

        with mock.patch(
            "maya_cython_compile.pipeline.subprocess.run",
            return_value=make_probe_completed_process(
                mayapy=mayapy,
                include_dir=include_dir,
                library_file=library_file,
                runtime_platform="linux",
            ),
        ):
            payload = probe_maya_runtime(mayapy, target_platform="linux")

        self.assertTrue(payload.probe_succeeded)
        self.assertEqual(payload.target_platform, "linux")
        self.assertEqual(payload.runtime_platform, "linux")
        self.assertTrue(payload.platform_matches_target)
        self.assertEqual(payload.include_dir, str(include_dir))
        self.assertEqual(payload.library_dir, str(library_file.parent))
        self.assertEqual(payload.library_name, "python3.11")
        self.assertEqual(payload.library_file, str(library_file))
        self.assertEqual(payload.extension_suffix, ".so")
        self.assertEqual(payload.soabi, "cpython-311")

    def test_ensure_maya_build_runtime_rejects_target_platform_mismatch(self) -> None:
        repo_root = make_temp_repo("pipeline-probe-mismatch")
        mayapy, include_dir, library_file = write_fake_maya_probe_layout(
            repo_root,
            library_filename="libpython3.11.so",
        )

        with mock.patch(
            "maya_cython_compile.pipeline.subprocess.run",
            return_value=make_probe_completed_process(
                mayapy=mayapy,
                include_dir=include_dir,
                library_file=library_file,
                runtime_platform="linux",
            ),
        ):
            payload = probe_maya_runtime(mayapy, target_platform="windows")

        self.assertFalse(payload.platform_matches_target)
        with self.assertRaises(CliError) as exc:
            ensure_maya_build_runtime(payload, mayapy)

        self.assertEqual(exc.exception.exit_code, DEPENDENCY_ERROR)
        self.assertIn("does not match mayapy runtime linux", str(exc.exception))

    def test_build_exports_probe_metadata_to_build_environment(self) -> None:
        repo_root = make_temp_repo("pipeline-build-env")
        write_multi_target_build_config(repo_root)
        env_path = repo_root / ".conda" / "maya-cython-build"
        env_path.mkdir(parents=True, exist_ok=True)
        mayapy, include_dir, library_file = write_fake_maya_probe_layout(
            repo_root,
            library_filename="libpython3.11.so",
        )
        wheel_path = repo_root / "dist" / "linux-2024" / "maya_tool-0.1.0-py3-none-any.whl"
        wheel_path.parent.mkdir(parents=True, exist_ok=True)
        wheel_path.write_text("", encoding="utf-8")
        config = resolve_config(
            repo_root,
            target="linux-2024",
            conda_exe=sys.executable,
            env_path=str(env_path),
            maya_py=str(mayapy),
        )
        captured_env: dict[str, str] = {}

        def capture_run_command(
            command: list[str],
            *,
            cwd: Path,
            env: dict[str, str] | None = None,
            verbose: bool = False,
            error_code: int,
        ) -> subprocess.CompletedProcess[str]:
            del command, cwd, verbose, error_code
            if env is not None:
                captured_env.update(env)
            return subprocess.CompletedProcess(args=["python"], returncode=0, stdout="", stderr="")

        with (
            mock.patch(
                "maya_cython_compile.pipeline.subprocess.run",
                return_value=make_probe_completed_process(
                    mayapy=mayapy,
                    include_dir=include_dir,
                    library_file=library_file,
                    runtime_platform="linux",
                ),
            ),
            mock.patch("maya_cython_compile.pipeline.prepare_build_tree", return_value=repo_root),
            mock.patch("maya_cython_compile.pipeline.run_command", side_effect=capture_run_command),
            mock.patch("maya_cython_compile.pipeline.latest_wheel", return_value=wheel_path),
        ):
            payload = build(config, force=True)

        self.assertEqual(payload["wheel"], str(wheel_path))
        self.assertEqual(captured_env["MAYA_PYTHON_INCLUDE"], str(include_dir))
        self.assertEqual(captured_env["MAYA_PYTHON_LIBDIR"], str(library_file.parent))
        self.assertEqual(captured_env["MAYA_PYTHON_LIBNAME"], "python3.11")
        self.assertEqual(captured_env["MAYA_PYTHON_LIBRARYFILE"], str(library_file))
        self.assertEqual(captured_env["MAYA_RUNTIME_PLATFORM"], "linux")
        self.assertEqual(captured_env["MAYA_TARGET_PLATFORM"], "linux")
        self.assertEqual(captured_env["MAYA_PYTHON_VERSION"], "3.11.9")
        self.assertEqual(captured_env["MAYA_PYTHON_EXT_SUFFIX"], ".so")
        self.assertEqual(captured_env["MAYA_PYTHON_SOABI"], "cpython-311")
