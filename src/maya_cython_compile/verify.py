from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import ResolvedConfig
from .errors import DEPENDENCY_ERROR, CliError
from .pipeline import (
    target_artifact_manifest_path,
    target_dist_dir,
    target_env_spec_path,
    target_module_root,
    target_smoke_extract_dir,
)


@dataclass(frozen=True, slots=True)
class VerifyStep:
    name: str
    command: list[str]
    cwd: Path
    env: dict[str, str] | None = None
    expect_json: bool = False


@dataclass(frozen=True, slots=True)
class VerifyScenario:
    name: str
    description: str
    requires_maya: bool
    step_builder: Callable[[ResolvedConfig, Path], list[VerifyStep]]


def list_scenarios() -> list[dict[str, Any]]:
    return [
        {
            "name": scenario.name,
            "description": scenario.description,
            "requires_maya": scenario.requires_maya,
        }
        for scenario in SCENARIOS.values()
    ]


def run_verification(
    config: ResolvedConfig,
    *,
    scenario_name: str,
    run_root: Path | None = None,
) -> dict[str, Any]:
    scenario = SCENARIOS.get(scenario_name)
    if scenario is None:
        available = ", ".join(sorted(SCENARIOS))
        raise CliError(
            f"Unknown verify scenario {scenario_name!r}. Available scenarios: {available}",
            DEPENDENCY_ERROR,
            error_code="verify_unknown_scenario",
            details={"scenario": scenario_name, "available_scenarios": list_scenarios()},
        )

    started_at = timestamp_now()
    run_dir = create_run_dir(config, scenario.name, run_root=run_root)
    steps_dir = run_dir / "steps"
    steps_dir.mkdir(parents=True, exist_ok=True)
    snapshot_inputs(config, run_dir)

    summary: dict[str, Any] = {
        "ok": False,
        "scenario": scenario.name,
        "description": scenario.description,
        "requires_maya": scenario.requires_maya,
        "repo_root": str(config.repo_root),
        "target": config.build.target_name,
        "run_dir": str(run_dir),
        "summary_path": str(run_dir / "summary.json"),
        "started_at": started_at,
        "artifacts": scenario_artifacts(config, run_dir),
        "commands": [],
    }

    try:
        for index, step in enumerate(scenario.step_builder(config, run_dir), start=1):
            step_result = run_step(step, steps_dir, index)
            commands = summary["commands"]
            assert isinstance(commands, list)
            commands.append(step_result)
            if step_result["returncode"] != 0:
                failure_payload = _coerce_mapping(step_result.get("stderr_json")) or _coerce_mapping(
                    step_result.get("stdout_json")
                )
                summary.update(
                    {
                        "stage": step.name,
                        "exit_code": step_result["returncode"],
                        "error_code": failure_payload.get("error_code")
                        if isinstance(failure_payload, dict)
                        else "verify_step_failed",
                        "message": failure_payload.get("message")
                        if isinstance(failure_payload, dict) and isinstance(failure_payload.get("message"), str)
                        else f"Verification scenario {scenario.name} failed at {step.name}.",
                        "stderr_tail": step_result["stderr_tail"],
                        "stdout_tail": step_result["stdout_tail"],
                        "failure_hint": failure_hint(step.name, step_result),
                    }
                )
                return raise_failure(summary, config, run_dir)

        summary.update(
            {
                "ok": True,
                "stage": "complete",
                "exit_code": 0,
                "message": f"Verification scenario {scenario.name} passed.",
            }
        )
        return finalize_summary(summary, config, run_dir)
    except CliError:
        raise
    except Exception as exc:
        summary.update(
            {
                "stage": "internal",
                "exit_code": DEPENDENCY_ERROR,
                "error_code": "verify_internal_error",
                "message": str(exc),
                "failure_hint": "Inspect summary.json and the step logs in the run directory.",
            }
        )
        return raise_failure(summary, config, run_dir)


def run_step(step: VerifyStep, steps_dir: Path, index: int) -> dict[str, Any]:
    stdout_path = steps_dir / f"{index:02d}-{step.name}.stdout.log"
    stderr_path = steps_dir / f"{index:02d}-{step.name}.stderr.log"
    env = os.environ.copy()
    if step.env:
        env.update(step.env)

    try:
        result = subprocess.run(
            step.command,
            cwd=str(step.cwd),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        stdout = result.stdout
        stderr = result.stderr
        returncode = result.returncode
    except FileNotFoundError as exc:
        stdout = ""
        stderr = str(exc)
        returncode = DEPENDENCY_ERROR

    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")

    return {
        "name": step.name,
        "argv": step.command,
        "cwd": str(step.cwd),
        "returncode": returncode,
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "stdout_json": parse_json_output(stdout) if step.expect_json else None,
        "stderr_json": parse_json_output(stderr),
        "stdout_tail": tail_lines(stdout),
        "stderr_tail": tail_lines(stderr),
    }


def parse_json_output(raw_output: str) -> dict[str, Any] | None:
    raw_output = raw_output.strip()
    if not raw_output:
        return None
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def tail_lines(raw_output: str, *, limit: int = 10) -> list[str]:
    lines = [line for line in raw_output.splitlines() if line.strip()]
    if len(lines) <= limit:
        return lines
    return lines[-limit:]


def failure_hint(step_name: str, step_result: dict[str, Any]) -> str:
    stderr_log = step_result["stderr_log"]
    if step_name == "doctor":
        return f"Resolve toolchain and mayapy mismatches, then rerun. See {stderr_log}."
    if step_name == "create_env":
        return f"Fix the Conda bootstrap inputs and inspect {stderr_log}."
    if step_name == "build":
        return f"Inspect the build logs and artifact metadata, then rerun. See {stderr_log}."
    if step_name == "smoke":
        return f"Check the extracted wheel and mayapy smoke logs in {stderr_log}."
    if step_name == "assemble":
        return f"Inspect the artifact manifest and assembled module paths. See {stderr_log}."
    if step_name == "package_cli":
        return f"Check wheel build output for the CLI package. See {stderr_log}."
    if step_name == "install_cli":
        return f"Fix the isolated venv install before rerunning. See {stderr_log}."
    return f"Inspect the failed step logs at {stderr_log}."


def raise_failure(summary: dict[str, Any], config: ResolvedConfig, run_dir: Path) -> dict[str, Any]:
    write_tree_snapshot(config, run_dir)
    write_summary(summary)
    raise CliError(
        str(summary["message"]),
        int(summary["exit_code"]),
        error_code=str(summary.get("error_code") or "verify_failed"),
        details=summary,
    )


def finalize_summary(summary: dict[str, Any], config: ResolvedConfig, run_dir: Path) -> dict[str, Any]:
    write_tree_snapshot(config, run_dir)
    write_summary(summary)
    return summary


def write_summary(summary: dict[str, Any]) -> None:
    finished = timestamp_now()
    summary["finished_at"] = finished
    summary_path = Path(str(summary["summary_path"]))
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def create_run_dir(config: ResolvedConfig, scenario_name: str, *, run_root: Path | None) -> Path:
    base_dir = (run_root or (config.repo_root / "build" / "agent-runs")).resolve()
    base_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{timestamp_now().replace(':', '').replace('-', '')}-{scenario_name}"
    run_dir = base_dir / stem
    suffix = 1
    while run_dir.exists():
        suffix += 1
        run_dir = base_dir / f"{stem}-{suffix}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def timestamp_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def snapshot_inputs(config: ResolvedConfig, run_dir: Path) -> None:
    input_dir = run_dir / "inputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    copy_if_exists(config.repo_root / "build-config.json", input_dir / "build-config.json")
    copy_if_exists(config.repo_root / "environment.yml", input_dir / "environment.yml")
    if config.local.config_path.exists():
        copy_if_exists(config.local.config_path, input_dir / config.local.config_path.name)


def copy_if_exists(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def write_tree_snapshot(config: ResolvedConfig, run_dir: Path) -> None:
    snapshot_path = run_dir / "filesystem.txt"
    tracked_paths = {
        "target_dist": target_dist_dir(config),
        "artifact_manifest": target_artifact_manifest_path(config),
        "env_spec": target_env_spec_path(config),
        "smoke_extract": target_smoke_extract_dir(config),
        "module_root": target_module_root(config),
    }
    lines: list[str] = []
    for label, path in tracked_paths.items():
        lines.append(f"[{label}] {path}")
        if not path.exists():
            lines.append("<missing>")
            lines.append("")
            continue
        if path.is_file():
            lines.append(path.name)
            lines.append("")
            continue
        for item in sorted(path.rglob("*")):
            relative = item.relative_to(path)
            suffix = "/" if item.is_dir() else ""
            lines.append(f"{relative}{suffix}")
        lines.append("")
    snapshot_path.write_text("\n".join(lines), encoding="utf-8")


def scenario_artifacts(config: ResolvedConfig, run_dir: Path) -> dict[str, str]:
    return {
        "run_dir": str(run_dir),
        "dist_dir": str(target_dist_dir(config)),
        "artifact_manifest": str(target_artifact_manifest_path(config)),
        "environment_file": str(target_env_spec_path(config)),
        "smoke_extract_dir": str(target_smoke_extract_dir(config)),
        "module_root": str(target_module_root(config)),
    }


def source_cli_globals(config: ResolvedConfig) -> list[str]:
    return [
        "--repo-root",
        str(config.repo_root),
        "--target",
        config.build.target_name,
        "--conda-exe",
        config.local.conda_exe,
        "--env-path",
        str(config.local.env_path),
        "--maya-py",
        str(config.local.maya_py),
        "--json",
        "--json-errors",
    ]


def source_cli_env(config: ResolvedConfig) -> dict[str, str]:
    del config
    source_path = str(Path(__file__).resolve().parents[1])
    existing = os.environ.get("PYTHONPATH", "")
    joined = os.pathsep.join(part for part in (source_path, existing) if part)
    return {"PYTHONPATH": joined}


def source_cli_step(config: ResolvedConfig, name: str, *args: str) -> VerifyStep:
    return VerifyStep(
        name=name,
        command=[sys.executable, "-m", "maya_cython_compile", *source_cli_globals(config), *args],
        cwd=config.repo_root,
        env=source_cli_env(config),
        expect_json=True,
    )


def venv_python(venv_root: Path) -> Path:
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    return venv_root / scripts_dir / ("python.exe" if os.name == "nt" else "python")


def venv_console_script(venv_root: Path) -> Path:
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    script_name = "maya-cython-compile.exe" if os.name == "nt" else "maya-cython-compile"
    return venv_root / scripts_dir / script_name


def venv_wheel_install_command(venv_root: Path, wheelhouse: Path) -> list[str]:
    return [
        str(venv_python(venv_root)),
        "-c",
        "\n".join(
            [
                "import subprocess",
                "import sys",
                "from pathlib import Path",
                "",
                "wheelhouse = Path(sys.argv[1])",
                "wheels = sorted(wheelhouse.glob('maya_cython_compile-*.whl'))",
                "if len(wheels) != 1:",
                "    raise SystemExit(",
                "        f'Expected exactly one maya-cython-compile wheel in {wheelhouse}, found {len(wheels)}.'",
                "    )",
                "",
                "raise SystemExit(",
                "    subprocess.call(",
                "        [sys.executable, '-m', 'pip', 'install', '--no-deps', '--force-reinstall', str(wheels[0])]",
                "    )",
                ")",
            ]
        ),
        str(wheelhouse),
    ]


def build_target_dry_run_steps(config: ResolvedConfig, run_dir: Path) -> list[VerifyStep]:
    del run_dir
    return [
        source_cli_step(config, "doctor", "doctor"),
        source_cli_step(config, "pipeline_dry_run", "run", "--dry-run", "--ensure-env"),
    ]


def build_target_run_steps(config: ResolvedConfig, run_dir: Path) -> list[VerifyStep]:
    del run_dir
    steps = [source_cli_step(config, "doctor", "doctor")]
    if not config.local.env_path.exists():
        steps.append(source_cli_step(config, "create_env", "create-env", "--force"))
    steps.extend(
        [
            source_cli_step(config, "build", "build", "--force"),
            source_cli_step(config, "smoke", "smoke", "--force"),
            source_cli_step(config, "assemble", "assemble", "--force"),
        ]
    )
    return steps


def build_installed_cli_steps(config: ResolvedConfig, run_dir: Path) -> list[VerifyStep]:
    wheelhouse = run_dir / "wheelhouse"
    venv_root = run_dir / "venv"
    console_script = venv_console_script(venv_root)
    return [
        VerifyStep(
            name="package_cli",
            command=[
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--wheel-dir",
                str(wheelhouse),
                str(config.repo_root),
            ],
            cwd=config.repo_root,
        ),
        VerifyStep(
            name="create_venv",
            command=[sys.executable, "-m", "venv", str(venv_root)],
            cwd=config.repo_root,
        ),
        VerifyStep(
            name="install_cli",
            command=venv_wheel_install_command(venv_root, wheelhouse),
            cwd=config.repo_root,
        ),
        VerifyStep(
            name="installed_config_show",
            command=[
                str(console_script),
                "--repo-root",
                str(config.repo_root),
                "--target",
                config.build.target_name,
                "--json",
                "--json-errors",
                "config",
                "show",
            ],
            cwd=config.repo_root,
            expect_json=True,
        ),
    ]


def _coerce_mapping(payload: Any) -> dict[str, Any] | None:
    return payload if isinstance(payload, dict) else None


SCENARIOS: dict[str, VerifyScenario] = {
    "installed-cli-config-show": VerifyScenario(
        name="installed-cli-config-show",
        description=(
            "Build the CLI wheel, install it into a fresh venv, "
            "and run config show from the installed entrypoint."
        ),
        requires_maya=False,
        step_builder=build_installed_cli_steps,
    ),
    "target-dry-run": VerifyScenario(
        name="target-dry-run",
        description="Run doctor plus a target-scoped run --dry-run --ensure-env preview through the source CLI.",
        requires_maya=True,
        step_builder=build_target_dry_run_steps,
    ),
    "target-run": VerifyScenario(
        name="target-run",
        description="Run doctor, build, smoke, and assemble against the selected target using the source CLI.",
        requires_maya=True,
        step_builder=build_target_run_steps,
    ),
}
