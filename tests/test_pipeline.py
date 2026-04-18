from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from maya_cython_compile.config import resolve_config
from maya_cython_compile.errors import DEPENDENCY_ERROR, SMOKE_ERROR, CliError
from maya_cython_compile.pipeline import (
    ARTIFACT_MANIFEST_FILENAME,
    build,
    conda_command,
    ensure_maya_build_runtime,
    probe_maya_runtime,
    python_version_matches_target,
    render_target_environment_yaml,
    smoke,
)
from maya_cython_compile.target_builder import ARTIFACT_METADATA_FILENAME, prepare_build_tree
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


def target_artifact_metadata(
    *,
    target_name: str,
    platform: str,
    maya_version: str,
    python_version: str,
    distribution_name: str = "maya-tool",
    package_name: str = "maya_tool",
    module_name: str,
    version: str = "0.1.0",
) -> dict[str, str | int]:
    return {
        "schema_version": 1,
        "target_name": target_name,
        "platform": platform,
        "maya_version": maya_version,
        "python_version": python_version,
        "distribution_name": distribution_name,
        "package_name": package_name,
        "module_name": module_name,
        "version": version,
    }


def write_fake_artifact_wheel(
    repo_root: Path,
    *,
    target_name: str,
    artifact_target_name: str | None = None,
    platform: str,
    maya_version: str,
    python_version: str,
    module_name: str,
    distribution_name: str = "maya-tool",
    package_name: str = "maya_tool",
    version: str = "0.1.0",
    write_manifest: bool = True,
) -> Path:
    dist_dir = repo_root / "dist" / target_name
    dist_dir.mkdir(parents=True, exist_ok=True)
    wheel_path = dist_dir / f"{distribution_name.replace('-', '_')}-{version}-py3-none-any.whl"
    metadata = target_artifact_metadata(
        target_name=artifact_target_name or target_name,
        platform=platform,
        maya_version=maya_version,
        python_version=python_version,
        distribution_name=distribution_name,
        package_name=package_name,
        module_name=module_name,
        version=version,
    )

    with zipfile.ZipFile(wheel_path, "w") as archive:
        archive.writestr(
            f"{distribution_name.replace('-', '_')}-{version}.dist-info/{ARTIFACT_METADATA_FILENAME}",
            json.dumps(metadata),
        )

    if write_manifest:
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
            payload = probe_maya_runtime(
                mayapy,
                target_platform="linux",
                target_python_version="3.11",
            )

        self.assertTrue(payload.probe_succeeded)
        self.assertEqual(payload.target_platform, "linux")
        self.assertEqual(payload.target_python_version, "3.11")
        self.assertEqual(payload.runtime_platform, "linux")
        self.assertTrue(payload.platform_matches_target)
        self.assertTrue(payload.python_matches_target)
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
            payload = probe_maya_runtime(
                mayapy,
                target_platform="windows",
                target_python_version="3.11",
            )

        self.assertFalse(payload.platform_matches_target)
        with self.assertRaises(CliError) as exc:
            ensure_maya_build_runtime(payload, mayapy)

        self.assertEqual(exc.exception.exit_code, DEPENDENCY_ERROR)
        self.assertIn("does not match mayapy runtime linux", str(exc.exception))

    def test_ensure_maya_build_runtime_rejects_target_python_mismatch(self) -> None:
        repo_root = make_temp_repo("pipeline-probe-python-mismatch")
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
            payload = probe_maya_runtime(
                mayapy,
                target_platform="linux",
                target_python_version="3.10",
            )

        self.assertFalse(payload.python_matches_target)
        with self.assertRaises(CliError) as exc:
            ensure_maya_build_runtime(payload, mayapy)

        self.assertEqual(exc.exception.exit_code, DEPENDENCY_ERROR)
        self.assertIn("Configured target Python 3.10 does not match mayapy runtime 3.11.9", str(exc.exception))

    def test_build_exports_probe_metadata_to_build_environment(self) -> None:
        repo_root = make_temp_repo("pipeline-build-env")
        write_multi_target_build_config(repo_root)
        env_path = repo_root / ".conda" / "maya-cython-build"
        env_path.mkdir(parents=True, exist_ok=True)
        mayapy, include_dir, library_file = write_fake_maya_probe_layout(
            repo_root,
            library_filename="libpython3.11.so",
        )
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
            write_fake_artifact_wheel(
                repo_root,
                target_name="linux-2024",
                platform="linux",
                maya_version="2024",
                python_version="3.11",
                module_name="MayaToolLinux",
                write_manifest=False,
            )
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
        ):
            payload = build(config, force=True)

        wheel_path = repo_root / "dist" / "linux-2024" / "maya_tool-0.1.0-py3-none-any.whl"
        manifest_path = repo_root / "dist" / "linux-2024" / ARTIFACT_MANIFEST_FILENAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["wheel"], str(wheel_path))
        self.assertEqual(payload["artifact_manifest"], str(manifest_path))
        self.assertEqual(captured_env["MAYA_PYTHON_INCLUDE"], str(include_dir))
        self.assertEqual(captured_env["MAYA_PYTHON_LIBDIR"], str(library_file.parent))
        self.assertEqual(captured_env["MAYA_PYTHON_LIBNAME"], "python3.11")
        self.assertEqual(captured_env["MAYA_PYTHON_LIBRARYFILE"], str(library_file))
        self.assertEqual(captured_env["MAYA_RUNTIME_PLATFORM"], "linux")
        self.assertEqual(captured_env["MAYA_TARGET_PLATFORM"], "linux")
        self.assertEqual(captured_env["MAYA_PYTHON_VERSION"], "3.11.9")
        self.assertEqual(captured_env["MAYA_PYTHON_EXT_SUFFIX"], ".so")
        self.assertEqual(captured_env["MAYA_PYTHON_SOABI"], "cpython-311")
        self.assertEqual(manifest["wheel"], wheel_path.name)
        self.assertEqual(manifest["sha256"], hashlib.sha256(wheel_path.read_bytes()).hexdigest())
        self.assertEqual(manifest["build"]["target_name"], "linux-2024")
        self.assertEqual(manifest["build"]["platform"], "linux")

    def test_smoke_rejects_manifest_hash_mismatch(self) -> None:
        repo_root = make_temp_repo("pipeline-smoke-hash-mismatch")
        write_multi_target_build_config(repo_root)
        wheel_path = write_fake_artifact_wheel(
            repo_root,
            target_name="linux-2024",
            platform="linux",
            maya_version="2024",
            python_version="3.11",
            module_name="MayaToolLinux",
        )
        manifest_path = repo_root / "dist" / "linux-2024" / ARTIFACT_MANIFEST_FILENAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        config = resolve_config(
            repo_root,
            target="linux-2024",
            maya_py=sys.executable,
        )

        with self.assertRaises(CliError) as exc:
            smoke(config, force=True)

        self.assertEqual(exc.exception.exit_code, SMOKE_ERROR)
        self.assertIn(wheel_path.name, str(exc.exception))
        self.assertIn("sha256=", str(exc.exception))

    def test_prepare_build_tree_writes_bdist_wheel_metadata_hook_without_runtime_file(self) -> None:
        repo_root = make_temp_repo("pipeline-build-tree")
        write_multi_target_build_config(repo_root)
        package_root = repo_root / "src" / "maya_tool"
        package_root.mkdir(parents=True, exist_ok=True)
        (package_root / "__init__.py").write_text("", encoding="utf-8")
        (package_root / "_cy_logic.py").write_text("VALUE = 1\n", encoding="utf-8")
        config = resolve_config(repo_root, target="linux-2024")

        build_root = prepare_build_tree(config)

        build_config = json.loads((build_root / "build-config.json").read_text(encoding="utf-8"))
        setup_py = (build_root / "setup.py").read_text(encoding="utf-8")
        self.assertNotIn("artifact_metadata_filename", build_config)
        self.assertFalse((build_root / "src" / "maya_tool" / ARTIFACT_METADATA_FILENAME).exists())
        self.assertIn('ARTIFACT_METADATA_FILE = "maya_cython_compile_artifact.json"', setup_py)
        self.assertIn('cmdclass={"build_py": build_py, "bdist_wheel": bdist_wheel}', setup_py)

    def test_smoke_rejects_wheel_from_other_target_even_in_selected_dist_dir(self) -> None:
        repo_root = make_temp_repo("pipeline-smoke-wrong-target")
        write_multi_target_build_config(repo_root)
        write_fake_artifact_wheel(
            repo_root,
            target_name="linux-2024",
            artifact_target_name="windows-2025",
            platform="windows",
            maya_version="2025",
            python_version="3.11",
            module_name="MayaToolWin",
        )
        config = resolve_config(
            repo_root,
            target="linux-2024",
            maya_py=sys.executable,
        )

        with self.assertRaises(CliError) as exc:
            smoke(config, force=True)

        self.assertEqual(exc.exception.exit_code, SMOKE_ERROR)
        self.assertIn("does not match selected target linux-2024", str(exc.exception))

    def test_render_target_environment_yaml_replaces_python_dependency(self) -> None:
        rendered = render_target_environment_yaml(
            "name: maya-cython-build\nchannels:\n  - defaults\ndependencies:\n  - python=3.11\n  - pip\n",
            "3.10",
        )

        self.assertIn("  - python=3.10\n", rendered)
        self.assertNotIn("  - python=3.11\n", rendered)

    def test_python_version_matches_target_accepts_prefix_match(self) -> None:
        self.assertTrue(python_version_matches_target("3.11.9", "3.11"))
        self.assertFalse(python_version_matches_target("3.11.9", "3.10"))

    def test_conda_command_uses_batch_launcher_on_windows(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows batch launcher requires Windows path semantics.")

        with mock.patch.dict("maya_cython_compile.conda.os.environ", {"COMSPEC": r"C:\Windows\System32\cmd.exe"}):
            command = conda_command(r"C:\Miniconda3\condabin\conda.bat", "env", "create")

        self.assertEqual(
            command,
            [r"C:\Windows\System32\cmd.exe", "/d", "/c", r"C:\Miniconda3\condabin\conda.bat", "env", "create"],
        )

    def test_conda_command_runs_non_batch_executable_directly(self) -> None:
        command = conda_command("/opt/miniconda3/bin/conda", "run", "--prefix", "/tmp/env")

        self.assertEqual(command, ["/opt/miniconda3/bin/conda", "run", "--prefix", "/tmp/env"])
