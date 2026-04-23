from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = ROOT / "scripts"
TMP_ROOT = ROOT / "build" / "test-tmp"
POWERSHELL = shutil.which("powershell")

FAKE_INVOKE_HELPER = """function Invoke-MayaCythonCompileCli {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$CliArgs,
        [string]$EnvPath = ""
    )

    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    $env:PYTHONPATH = Join-Path $repoRoot "src"

    @{
        CliArgs = $CliArgs
        EnvPath = $EnvPath
        PYTHONPATH = $env:PYTHONPATH
    } | ConvertTo-Json -Compress
}
"""


def make_temp_repo(name: str) -> Path:
    repo_root = TMP_ROOT / name
    if repo_root.exists():
        shutil.rmtree(repo_root)
    (repo_root / "scripts").mkdir(parents=True, exist_ok=True)
    return repo_root


def copy_wrapper(repo_root: Path, wrapper_name: str) -> Path:
    wrapper_path = repo_root / "scripts" / wrapper_name
    shutil.copy2(SCRIPTS_ROOT / wrapper_name, wrapper_path)
    (repo_root / "scripts" / "_invoke-cli.ps1").write_text(FAKE_INVOKE_HELPER, encoding="utf-8")
    return wrapper_path


class WrapperTests(unittest.TestCase):
    def setUp(self) -> None:
        if POWERSHELL is None:
            self.skipTest("powershell is required for wrapper tests.")

    def invoke_wrapper(self, wrapper_name: str, *args: str) -> tuple[dict[str, object], Path]:
        assert POWERSHELL is not None
        repo_root = make_temp_repo(f"wrapper-{wrapper_name.replace('.ps1', '')}")
        wrapper_path = copy_wrapper(repo_root, wrapper_name)
        result = subprocess.run(
            [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(wrapper_path), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return json.loads(result.stdout), repo_root

    def test_create_env_wrapper_forwards_target_without_baked_in_runtime_defaults(self) -> None:
        payload, repo_root = self.invoke_wrapper(
            "create-conda-env.ps1",
            "-Target",
            "linux-2024",
            "-EnvPath",
            ".conda/linux-2024",
            "-DryRun",
        )

        self.assertEqual(
            payload["CliArgs"],
            [
                "create-env",
                "--repo-root",
                str(repo_root),
                "--target",
                "linux-2024",
                "--env-path",
                ".conda/linux-2024",
                "--dry-run",
            ],
        )
        self.assertEqual(payload["EnvPath"], ".conda/linux-2024")
        self.assertEqual(payload["PYTHONPATH"], str(repo_root / "src"))

    def test_build_wrapper_forwards_target_local_overrides_and_safety_flags(self) -> None:
        payload, repo_root = self.invoke_wrapper(
            "build-package.ps1",
            "-Target",
            "linux-2024",
            "-EnvPath",
            ".conda/linux-2024",
            "-MayaPy",
            "C:/maya/bin/mayapy.exe",
            "-DryRun",
            "-Force",
        )

        self.assertEqual(
            payload["CliArgs"],
            [
                "build",
                "--repo-root",
                str(repo_root),
                "--target",
                "linux-2024",
                "--env-path",
                ".conda/linux-2024",
                "--maya-py",
                "C:/maya/bin/mayapy.exe",
                "--dry-run",
                "--force",
            ],
        )

    def test_assemble_wrapper_keeps_target_selection_thin(self) -> None:
        payload, repo_root = self.invoke_wrapper(
            "assemble-module.ps1",
            "-Target",
            "windows-2025",
            "-EnvPath",
            ".conda/windows-2025",
            "-Force",
        )

        self.assertEqual(
            payload["CliArgs"],
            [
                "assemble",
                "--repo-root",
                str(repo_root),
                "--target",
                "windows-2025",
                "--env-path",
                ".conda/windows-2025",
                "--force",
            ],
        )
        cli_args = cast(list[Any], payload["CliArgs"])
        self.assertNotIn("--maya-version", cli_args)
        self.assertNotIn("--module-name", cli_args)
        self.assertNotIn("--platform", cli_args)

    def test_run_wrapper_forwards_full_workflow_flags(self) -> None:
        payload, repo_root = self.invoke_wrapper(
            "run-pipeline.ps1",
            "-Target",
            "linux-2024",
            "-EnvPath",
            ".conda/linux-2024",
            "-MayaPy",
            "/usr/autodesk/maya2024/bin/mayapy",
            "-EnsureEnv",
            "-SkipSmoke",
            "-SkipAssemble",
            "-SkipPackage",
            "-DryRun",
            "-Force",
        )

        self.assertEqual(
            payload["CliArgs"],
            [
                "run",
                "--repo-root",
                str(repo_root),
                "--target",
                "linux-2024",
                "--env-path",
                ".conda/linux-2024",
                "--maya-py",
                "/usr/autodesk/maya2024/bin/mayapy",
                "--ensure-env",
                "--skip-smoke",
                "--skip-assemble",
                "--skip-package",
                "--dry-run",
                "--force",
            ],
        )
