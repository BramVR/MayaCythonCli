from __future__ import annotations

import argparse
import json
import sys
import tomllib
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

from .config import ResolvedConfig, resolve_config
from .errors import INTERRUPTED_ERROR, USAGE_ERROR, CliError
from .pipeline import assemble, build, create_env, doctor, run_pipeline, show_config, smoke
from .verify import list_scenarios, run_verification

BOOL_GLOBAL_FLAGS = {"--json", "--json-errors", "--verbose", "--version"}
VALUE_GLOBAL_FLAGS = {
    "--repo-root",
    "--config",
    "--target",
    "--conda-exe",
    "--env-path",
    "--maya-py",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="maya-cython-compile",
        description="Build Maya-targeted Cython packages from a standard Python environment.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}",
    )
    parser.add_argument("--repo-root", default=".", help="Repo root used for config and outputs.")
    parser.add_argument("--config", help="Optional local config file path.")
    parser.add_argument("--target", help="Select a named build target.")
    parser.add_argument("--json", action="store_true", help="Emit JSON to stdout.")
    parser.add_argument(
        "--json-errors",
        action="store_true",
        help="Emit one JSON error object to stderr on failure.",
    )
    parser.add_argument("--verbose", action="store_true", help="Print subprocess commands to stderr.")
    parser.add_argument("--conda-exe", help="Override Conda executable path.")
    parser.add_argument("--env-path", help="Override local Conda environment path.")
    parser.add_argument("--maya-py", help="Override mayapy path.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    config_parser = subparsers.add_parser("config", help="Inspect resolved configuration.")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)
    config_subparsers.add_parser("show", help="Show resolved config.")

    subparsers.add_parser("doctor", help="Check local toolchain paths and Maya runtime discovery.")
    create_env_parser = subparsers.add_parser(
        "create-env",
        help="Create the local Conda build environment, or refresh it when --force allows replacement.",
    )
    add_safety_flags(create_env_parser)

    build_command_parser = subparsers.add_parser("build", help="Build the configured Maya wheel.")
    add_safety_flags(build_command_parser)

    smoke_parser = subparsers.add_parser("smoke", help="Run the configured smoke import under mayapy.")
    add_safety_flags(smoke_parser)

    assemble_parser = subparsers.add_parser("assemble", help="Assemble the Maya module layout.")
    add_safety_flags(assemble_parser)

    run_parser = subparsers.add_parser("run", help="Run the full pipeline.")
    add_safety_flags(run_parser)
    run_parser.add_argument(
        "--ensure-env",
        action="store_true",
        help="Create the Conda env first when it is missing.",
    )
    run_parser.add_argument("--skip-smoke", action="store_true", help="Skip mayapy smoke validation.")
    run_parser.add_argument("--skip-assemble", action="store_true", help="Skip module assembly.")

    verify_parser = subparsers.add_parser("verify", help="Run agent-facing verification scenarios.")
    verify_parser.add_argument(
        "--scenario",
        default="target-run",
        help="Verification scenario name. Use --list-scenarios to inspect the built-ins.",
    )
    verify_parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="List available verification scenarios and exit.",
    )
    verify_parser.add_argument(
        "--run-root",
        help="Optional directory where verify run bundles should be written.",
    )

    return parser


def add_safety_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned deletions and subprocesses without changing files.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow deleting existing outputs without prompting.",
    )


def get_version() -> str:
    try:
        return package_version("maya-cython-compile")
    except PackageNotFoundError:
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        if pyproject_path.exists():
            project = tomllib.loads(pyproject_path.read_text(encoding="utf-8")).get("project", {})
            version = project.get("version")
            if isinstance(version, str) and version:
                return version
        return "0+unknown"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    effective_argv = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(normalize_argv(effective_argv))

    try:
        config = resolve_config(
            Path(args.repo_root),
            config_path=args.config,
            target=args.target,
            conda_exe=args.conda_exe,
            env_path=args.env_path,
            maya_py=args.maya_py,
        )
        payload = dispatch(args, config)
    except CliError as exc:
        emit_error(
            exc,
            as_json=bool(getattr(args, "json_errors", False)),
            command=getattr(args, "command", None),
            target=getattr(args, "target", None),
        )
        return exc.exit_code
    except ValueError as exc:
        emit_error(
            CliError(str(exc), USAGE_ERROR, error_code="usage_error"),
            as_json=bool(getattr(args, "json_errors", False)),
            command=getattr(args, "command", None),
            target=getattr(args, "target", None),
        )
        return USAGE_ERROR
    except KeyboardInterrupt:
        emit_error(
            CliError("Interrupted.", INTERRUPTED_ERROR, error_code="interrupted"),
            as_json=bool(getattr(args, "json_errors", False)),
            command=getattr(args, "command", None),
            target=getattr(args, "target", None),
        )
        return INTERRUPTED_ERROR

    emit(payload, as_json=bool(args.json))
    return 0


def dispatch(args: argparse.Namespace, config: ResolvedConfig) -> dict[str, Any]:
    if args.command == "config":
        if args.config_command == "show":
            return {"config": show_config(config)}
        raise ValueError(f"Unsupported config command: {args.config_command}")
    if args.command == "doctor":
        return doctor(config)
    if args.command == "create-env":
        return create_env(
            config,
            verbose=bool(args.verbose),
            dry_run=bool(args.dry_run),
            force=bool(args.force),
        )
    if args.command == "build":
        return build(
            config,
            verbose=bool(args.verbose),
            dry_run=bool(args.dry_run),
            force=bool(args.force),
        )
    if args.command == "smoke":
        return smoke(
            config,
            verbose=bool(args.verbose),
            dry_run=bool(args.dry_run),
            force=bool(args.force),
        )
    if args.command == "assemble":
        return assemble(
            config,
            dry_run=bool(args.dry_run),
            force=bool(args.force),
        )
    if args.command == "run":
        return run_pipeline(
            config,
            verbose=bool(args.verbose),
            ensure_env=bool(args.ensure_env),
            skip_smoke=bool(args.skip_smoke),
            skip_assemble=bool(args.skip_assemble),
            dry_run=bool(args.dry_run),
            force=bool(args.force),
        )
    if args.command == "verify":
        if args.list_scenarios:
            return {"scenarios": list_scenarios()}
        run_root = None
        if args.run_root:
            candidate_run_root = Path(args.run_root)
            run_root = (
                config.repo_root / candidate_run_root
                if not candidate_run_root.is_absolute()
                else candidate_run_root
            )
        return run_verification(
            config,
            scenario_name=args.scenario,
            run_root=run_root,
        )
    raise ValueError(f"Unsupported command: {args.command}")


def normalize_argv(argv: list[str] | None) -> list[str] | None:
    if argv is None:
        return None

    prefix: list[str] = []
    rest: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--":
            rest.extend(argv[index:])
            break
        if token in BOOL_GLOBAL_FLAGS:
            prefix.append(token)
            index += 1
            continue
        if token in VALUE_GLOBAL_FLAGS and index + 1 < len(argv):
            prefix.extend([token, argv[index + 1]])
            index += 2
            continue
        matched = False
        for flag in VALUE_GLOBAL_FLAGS:
            if token.startswith(f"{flag}="):
                prefix.append(token)
                matched = True
                break
        if matched:
            index += 1
            continue
        rest.append(token)
        index += 1
    return prefix + rest


def emit(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
        return

    for line in render_text(payload):
        print(line)


def render_text(payload: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if payload.get("dry_run"):
        return render_dry_run_text(payload)

    if "scenarios" in payload:
        lines.append("Verify scenarios")
        for scenario in payload["scenarios"]:
            if not isinstance(scenario, dict):
                continue
            lines.append(f"{scenario.get('name')}: {scenario.get('description')}")
        return lines

    if "scenario" in payload and "commands" in payload:
        lines.append(f"Verify: {payload['scenario']}")
        lines.append(f"ok: {payload.get('ok')}")
        lines.append(f"stage: {payload.get('stage')}")
        lines.append(f"run_dir: {payload.get('run_dir')}")
        lines.append(f"summary_path: {payload.get('summary_path')}")
        lines.append(f"message: {payload.get('message')}")
        return lines

    if "checks" in payload:
        lines.append("Doctor")
        for key, value in payload["checks"].items():
            lines.append(f"{key}: {'ok' if value else 'missing'}")
        maya_runtime = payload.get("maya_runtime", {})
        for key in (
            "maya_py",
            "target_platform",
            "target_python_version",
            "runtime_platform",
            "platform_matches_target",
            "python_version",
            "python_matches_target",
            "include_dir",
            "library_dir",
            "library_name",
            "library_file",
            "extension_suffix",
            "soabi",
            "error",
        ):
            lines.append(f"{key}: {maya_runtime.get(key)}")
        return lines

    if "config" in payload:
        lines.append("Config")
        for key, value in payload["config"].items():
            lines.append(f"{key}: {value}")
        return lines

    for key, value in payload.items():
        lines.append(f"{key}: {value}")
    return lines


def emit_error(exc: CliError, *, as_json: bool, command: str | None, target: str | None) -> None:
    if as_json:
        print(json.dumps(error_payload(exc, command=command, target=target), indent=2), file=sys.stderr)
        return
    print(str(exc), file=sys.stderr)


def error_payload(exc: CliError, *, command: str | None, target: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "message": str(exc), "exit_code": exc.exit_code}
    if command:
        payload["command"] = command
    if target:
        payload["target"] = target
    if exc.error_code:
        payload["error_code"] = exc.error_code
    payload.update(exc.details)
    return payload


def render_dry_run_text(payload: dict[str, Any]) -> list[str]:
    lines = ["Dry run"]
    if "steps" in payload:
        for step_name, step_payload in payload["steps"].items():
            lines.append(f"[{step_name}]")
            lines.extend(render_dry_run_section(step_payload))
        return lines
    return lines + render_dry_run_section(payload)


def render_dry_run_section(payload: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if "command" in payload:
        lines.append(f"command: {payload['command']}")

    deletions = payload.get("delete", [])
    if deletions:
        for item in deletions:
            lines.append(f"delete: {item['path']} ({item['reason']})")
    else:
        lines.append("delete: none")

    if "would_run" in payload:
        lines.append(f"would_run: {' '.join(payload['would_run'])}")

    for key, value in payload.items():
        if key in {"dry_run", "command", "delete", "would_run"}:
            continue
        lines.append(f"{key}: {value}")
    return lines
