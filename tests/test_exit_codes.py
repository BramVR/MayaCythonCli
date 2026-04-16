from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TMP_ROOT = ROOT / "build" / "test-tmp"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from maya_cython_compile.cli import main
from maya_cython_compile.errors import ASSEMBLE_ERROR, SMOKE_ERROR


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


class ExitCodeTests(unittest.TestCase):
    def test_main_smoke_returns_smoke_exit_code_when_wheel_is_missing(self) -> None:
        repo_root = make_temp_repo("cli-smoke-missing-wheel")
        write_build_config(repo_root)

        exit_code = main(
            [
                "--repo-root",
                str(repo_root),
                "smoke",
                "--maya-py",
                sys.executable,
            ]
        )

        self.assertEqual(exit_code, SMOKE_ERROR)

    def test_main_assemble_returns_assemble_exit_code_when_wheel_is_missing(self) -> None:
        repo_root = make_temp_repo("cli-assemble-missing-wheel")
        write_build_config(repo_root)

        exit_code = main(
            [
                "--repo-root",
                str(repo_root),
                "assemble",
            ]
        )

        self.assertEqual(exit_code, ASSEMBLE_ERROR)
