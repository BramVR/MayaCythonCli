from __future__ import annotations

import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TMP_ROOT = ROOT / "build" / "test-tmp"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from maya_cython_compile.config import DEFAULT_PYTHON_VERSION, DEFAULT_TARGET_NAME, resolve_config


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
                        "python_version": "3.10",
                    },
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


class ConfigTests(unittest.TestCase):
    def test_resolve_config_prefers_conda_from_path_and_target_env_default(self) -> None:
        repo_root = make_temp_repo("config-default-conda")
        write_build_config(repo_root)
        discovered = r"C:\Miniconda3\condabin\conda.exe" if os.name == "nt" else "/opt/miniconda3/bin/conda"

        with patch("maya_cython_compile.conda.shutil.which", return_value=discovered):
            config = resolve_config(repo_root)

        self.assertEqual(config.build.target_name, DEFAULT_TARGET_NAME)
        self.assertEqual(config.build.platform, "windows")
        self.assertEqual(config.build.python_version, "3.11")
        self.assertEqual(config.local.conda_exe, discovered)
        self.assertEqual(config.local.env_path, (repo_root / ".conda" / DEFAULT_TARGET_NAME).resolve())

    def test_resolve_config_uses_platform_default_conda_when_path_lookup_misses(self) -> None:
        repo_root = make_temp_repo("config-default-conda-platform-fallback")
        write_build_config(repo_root)

        with patch("maya_cython_compile.conda.shutil.which", return_value=None):
            config = resolve_config(repo_root)

        expected = (
            str(Path.home() / "anaconda3" / "condabin" / "conda.bat")
            if os.name == "nt"
            else "conda"
        )
        self.assertEqual(config.local.conda_exe, expected)

    def test_resolve_config_uses_local_file(self) -> None:
        repo_root = make_temp_repo("config-local-file")
        write_build_config(repo_root)
        (repo_root / ".maya-cython-compile.json").write_text(
            json.dumps(
                {
                    "conda_exe": "tools/conda.bat",
                    "env_path": ".conda/custom-build",
                    "maya_py": "maya/bin/mayapy.exe",
                }
            ),
            encoding="utf-8",
        )

        config = resolve_config(repo_root)

        self.assertEqual(config.local.conda_exe, str((repo_root / "tools/conda.bat").resolve()))
        self.assertEqual(config.local.env_path, (repo_root / ".conda/custom-build").resolve())
        self.assertEqual(config.local.maya_py, (repo_root / "maya/bin/mayapy.exe").resolve())

    def test_build_default_target_is_used_when_no_override_is_set(self) -> None:
        repo_root = make_temp_repo("config-build-default-target")
        write_multi_target_build_config(repo_root)

        config = resolve_config(repo_root)

        self.assertEqual(config.build.target_name, "windows-2025")
        self.assertEqual(config.build.module_name, "MayaToolWin")
        self.assertEqual(config.build.maya_version, "2025")
        self.assertEqual(config.build.python_version, "3.11")

    def test_local_target_overrides_build_default_target(self) -> None:
        repo_root = make_temp_repo("config-local-target")
        write_multi_target_build_config(repo_root)
        (repo_root / ".maya-cython-compile.json").write_text(
            json.dumps({"target": "linux-2024"}),
            encoding="utf-8",
        )

        config = resolve_config(repo_root)

        self.assertEqual(config.build.target_name, "linux-2024")
        self.assertEqual(config.build.platform, "linux")
        self.assertEqual(config.build.module_name, "MayaToolLinux")
        self.assertEqual(config.build.python_version, "3.10")

    def test_target_precedence_cli_over_environment_and_local(self) -> None:
        repo_root = make_temp_repo("config-overrides")
        write_multi_target_build_config(repo_root)
        (repo_root / ".maya-cython-compile.json").write_text(
            json.dumps({"target": "linux-2024"}),
            encoding="utf-8",
        )
        with patch.dict(
            os.environ,
            {
                "MAYA_CYTHON_COMPILE_TARGET": "linux-2024",
                "MAYA_CYTHON_COMPILE_CONDA_EXE": r"C:\env\conda.bat",
                "MAYA_CYTHON_COMPILE_ENV_PATH": r"C:\env\build-env",
                "MAYA_CYTHON_COMPILE_MAYA_PY": r"C:\env\mayapy.exe",
            },
            clear=False,
        ):
            config = resolve_config(
                repo_root,
                target="windows-2025",
                conda_exe=r"C:\override\conda.bat",
                env_path=r"C:\override\build-env",
                maya_py=r"C:\override\mayapy.exe",
            )

        self.assertEqual(config.build.target_name, "windows-2025")
        self.assertEqual(config.local.conda_exe, r"C:\override\conda.bat")
        self.assertEqual(str(config.local.env_path), r"C:\override\build-env")
        self.assertEqual(str(config.local.maya_py), r"C:\override\mayapy.exe")

    def test_target_specific_local_paths_override_root_local_paths(self) -> None:
        repo_root = make_temp_repo("config-target-local-paths")
        write_multi_target_build_config(repo_root)
        (repo_root / ".maya-cython-compile.json").write_text(
            json.dumps(
                {
                    "target": "linux-2024",
                    "conda_exe": "tools/root-conda",
                    "env_path": ".conda/root-build",
                    "maya_py": "maya/root/mayapy",
                    "targets": {
                        "linux-2024": {
                            "env_path": ".conda/linux-build",
                            "maya_py": "maya/linux/mayapy",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        config = resolve_config(repo_root)

        self.assertEqual(config.local.conda_exe, str((repo_root / "tools/root-conda").resolve()))
        self.assertEqual(config.local.env_path, (repo_root / ".conda/linux-build").resolve())
        self.assertEqual(config.local.maya_py, (repo_root / "maya/linux/mayapy").resolve())

    def test_resolve_config_uses_default_python_version_when_not_declared(self) -> None:
        repo_root = make_temp_repo("config-default-python-version")
        write_build_config(repo_root)
        payload = json.loads((repo_root / "build-config.json").read_text(encoding="utf-8"))
        payload.pop("python_version", None)
        (repo_root / "build-config.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

        config = resolve_config(repo_root)

        self.assertEqual(config.build.python_version, DEFAULT_PYTHON_VERSION)
