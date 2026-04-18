from __future__ import annotations

import io
import json
import os
import shutil
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from maya_cython_compile.cli import main
from probe_fixtures import TMP_ROOT, make_temp_repo


def write_host_build_config(repo_root: Path) -> str:
    platform = {
        "win32": "windows",
        "linux": "linux",
        "darwin": "macos",
    }[sys.platform]
    target_name = f"{platform}-host"
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
                "default_target": target_name,
                "targets": {
                    target_name: {
                        "platform": platform,
                        "module_name": "HostTool",
                        "maya_version": "2025",
                        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
                    }
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return target_name


def write_probe_sitecustomize(repo_root: Path, *, library_filename: str) -> Path:
    include_dir = repo_root / "fake-maya" / "include"
    library_dir = repo_root / "fake-maya" / "lib"
    include_dir.mkdir(parents=True, exist_ok=True)
    library_dir.mkdir(parents=True, exist_ok=True)
    (library_dir / library_filename).write_text("", encoding="utf-8")
    shim_dir = repo_root / "probe-shim"
    shim_dir.mkdir(parents=True, exist_ok=True)
    (shim_dir / "sitecustomize.py").write_text(
        "\n".join(
            [
                "import sysconfig",
                f"INCLUDE_DIR = {str(include_dir)!r}",
                f"LIB_DIR = {str(library_dir)!r}",
                f"LIBRARY = {library_filename!r}",
                "REAL_GET_PATH = sysconfig.get_path",
                "REAL_GET_CONFIG_VAR = sysconfig.get_config_var",
                "",
                "def _patched_get_path(name, *args, **kwargs):",
                "    if name in {'include', 'platinclude'}:",
                "        return INCLUDE_DIR",
                "    return REAL_GET_PATH(name, *args, **kwargs)",
                "",
                "def _patched_get_config_var(name):",
                "    if name in {'LIBDIR', 'LIBPL'}:",
                "        return LIB_DIR",
                "    if name in {'LIBRARY', 'LDLIBRARY', 'INSTSONAME'}:",
                "        return LIBRARY",
                "    return REAL_GET_CONFIG_VAR(name)",
                "",
                "sysconfig.get_path = _patched_get_path",
                "sysconfig.get_config_var = _patched_get_config_var",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return shim_dir


class VerifyTests(unittest.TestCase):
    def test_main_verify_lists_scenarios(self) -> None:
        repo_root = make_temp_repo("verify-list")
        write_host_build_config(repo_root)
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = main(["--repo-root", str(repo_root), "verify", "--json", "--list-scenarios"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        scenario_names = {item["name"] for item in payload["scenarios"]}
        self.assertIn("target-run", scenario_names)
        self.assertIn("target-dry-run", scenario_names)
        self.assertIn("installed-cli-config-show", scenario_names)

    def test_verify_target_dry_run_writes_repro_bundle(self) -> None:
        repo_root = make_temp_repo("verify-target-dry-run")
        target_name = write_host_build_config(repo_root)
        shim_dir = write_probe_sitecustomize(repo_root, library_filename="python311.lib")
        run_root = make_temp_repo("verify-target-dry-run-runs")
        stdout = io.StringIO()

        with redirect_stdout(stdout), mock.patch.dict(os.environ, {"PYTHONPATH": str(shim_dir)}, clear=False):
            exit_code = main(
                [
                    "--repo-root",
                    str(repo_root),
                    "--target",
                    target_name,
                    "--conda-exe",
                    sys.executable,
                    "--env-path",
                    str(repo_root / ".conda" / target_name),
                    "--maya-py",
                    sys.executable,
                    "verify",
                    "--scenario",
                    "target-dry-run",
                    "--json",
                    "--run-root",
                    str(run_root),
                ]
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["stage"], "complete")
        self.assertEqual([command["name"] for command in payload["commands"]], ["doctor", "pipeline_dry_run"])
        run_dir = Path(payload["run_dir"])
        self.assertTrue(run_dir.is_dir())
        self.assertTrue((run_dir / "summary.json").exists())
        self.assertTrue((run_dir / "filesystem.txt").exists())
        self.assertTrue((run_dir / "steps" / "01-doctor.stdout.log").exists())
        self.assertTrue((run_dir / "steps" / "02-pipeline_dry_run.stdout.log").exists())
        self.assertEqual(payload["commands"][0]["stdout_json"]["config"]["target"], target_name)
        self.assertTrue(payload["commands"][1]["stdout_json"]["dry_run"])

    def test_verify_installed_cli_config_show_runs_from_fresh_venv(self) -> None:
        run_root = TMP_ROOT / "verify-installed-cli"
        if run_root.exists():
            shutil.rmtree(run_root)
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = main(
                [
                    "--repo-root",
                    str(ROOT),
                    "verify",
                    "--scenario",
                    "installed-cli-config-show",
                    "--json",
                    "--run-root",
                    str(run_root),
                ]
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(
            [command["name"] for command in payload["commands"]],
            ["package_cli", "create_venv", "install_cli", "installed_config_show"],
        )
        self.assertEqual(payload["commands"][-1]["stdout_json"]["config"]["package_name"], "maya_tool")
        self.assertTrue(Path(payload["run_dir"]).is_dir())
