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

from maya_cython_compile.config import resolve_config


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


class ConfigTests(unittest.TestCase):
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

        self.assertEqual(config.local.conda_exe, (repo_root / "tools/conda.bat").resolve())
        self.assertEqual(config.local.env_path, (repo_root / ".conda/custom-build").resolve())
        self.assertEqual(config.local.maya_py, (repo_root / "maya/bin/mayapy.exe").resolve())

    def test_cli_overrides_beat_environment(self) -> None:
        repo_root = make_temp_repo("config-overrides")
        write_build_config(repo_root)
        with patch.dict(
            os.environ,
            {
                "MAYA_CYTHON_COMPILE_CONDA_EXE": r"C:\env\conda.bat",
                "MAYA_CYTHON_COMPILE_ENV_PATH": r"C:\env\build-env",
                "MAYA_CYTHON_COMPILE_MAYA_PY": r"C:\env\mayapy.exe",
            },
            clear=False,
        ):
            config = resolve_config(
                repo_root,
                conda_exe=r"C:\override\conda.bat",
                env_path=r"C:\override\build-env",
                maya_py=r"C:\override\mayapy.exe",
            )

        self.assertEqual(str(config.local.conda_exe), r"C:\override\conda.bat")
        self.assertEqual(str(config.local.env_path), r"C:\override\build-env")
        self.assertEqual(str(config.local.maya_py), r"C:\override\mayapy.exe")
