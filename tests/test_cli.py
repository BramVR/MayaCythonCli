from __future__ import annotations

import io
import json
import shutil
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TMP_ROOT = ROOT / "build" / "test-tmp"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from maya_cython_compile.cli import build_parser, main


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


class CliTests(unittest.TestCase):
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
