from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import ResolvedConfig, as_dict
from .errors import (
    ASSEMBLE_ERROR,
    BUILD_ERROR,
    CliError,
    DEPENDENCY_ERROR,
    INTERRUPTED_ERROR,
    SMOKE_ERROR,
    USAGE_ERROR,
)
from .target_builder import prepare_build_tree


@dataclass(frozen=True, slots=True)
class DeletionTarget:
    path: Path
    reason: str


def show_config(config: ResolvedConfig) -> dict[str, Any]:
    return as_dict(config)


def doctor(config: ResolvedConfig) -> dict[str, Any]:
    maya = probe_maya_runtime(config.local.maya_py)
    return {
        "config": show_config(config),
        "checks": {
            "conda_exe_exists": config.local.conda_exe.exists(),
            "env_exists": config.local.env_path.exists(),
            "maya_py_exists": config.local.maya_py.exists(),
            "maya_include_exists": maya["include_dir"] is not None,
            "maya_lib_exists": maya["lib_dir"] is not None and maya["lib_name"] is not None,
        },
        "maya_runtime": maya,
    }


def create_env(
    config: ResolvedConfig,
    *,
    verbose: bool = False,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    if not config.local.conda_exe.exists():
        raise CliError(f"Conda was not found at {config.local.conda_exe}", DEPENDENCY_ERROR)

    deletion_targets = plan_create_env_refresh(config)
    command = [
        "cmd.exe",
        "/c",
        str(config.local.conda_exe),
        "env",
        "create",
        "--prefix",
        str(config.local.env_path),
    ]
    if deletion_targets:
        command.append("--force")
    command.extend(["--file", str(config.repo_root / "environment.yml")])

    if dry_run:
        return render_dry_run(
            "create-env",
            deletion_targets,
            command=command,
            details={"env_path": str(config.local.env_path)},
        )

    require_confirmation(
        "create-env",
        deletion_targets,
        force=force,
    )
    run_command(command, cwd=config.repo_root, verbose=verbose, error_code=DEPENDENCY_ERROR)
    return {"env_path": str(config.local.env_path)}


def build(
    config: ResolvedConfig,
    *,
    verbose: bool = False,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    if not config.local.env_path.exists():
        raise CliError(
            f"Conda environment missing: {config.local.env_path}. Run create-env first.",
            DEPENDENCY_ERROR,
        )

    maya = probe_maya_runtime(config.local.maya_py)
    if not maya["include_dir"] or not maya["lib_dir"] or not maya["lib_name"]:
        raise CliError(f"Could not resolve Maya Python runtime from {config.local.maya_py}", DEPENDENCY_ERROR)

    deletion_targets = plan_build_cleanup(config.repo_root)
    dist_dir = config.repo_root / "dist"
    command = [
        "cmd.exe",
        "/c",
        str(config.local.conda_exe),
        "run",
        "--prefix",
        str(config.local.env_path),
        "python",
        "setup.py",
        "bdist_wheel",
        "--dist-dir",
        str(dist_dir),
    ]
    if dry_run:
        return render_dry_run(
            "build",
            deletion_targets,
            command=command,
            details={"dist_dir": str(dist_dir)},
        )

    require_confirmation(
        "build",
        deletion_targets,
        force=force,
    )
    delete_paths(deletion_targets)
    build_tree = prepare_build_tree(config)
    dist_dir.mkdir(parents=True, exist_ok=True)

    temp_root = config.repo_root / "build" / "tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["MAYA_PYTHON_INCLUDE"] = str(maya["include_dir"])
    env["MAYA_PYTHON_LIBDIR"] = str(maya["lib_dir"])
    env["MAYA_PYTHON_LIBNAME"] = str(maya["lib_name"])
    env["TEMP"] = str(temp_root)
    env["TMP"] = str(temp_root)

    run_command(command, cwd=build_tree, env=env, verbose=verbose, error_code=BUILD_ERROR)
    wheel = latest_wheel(config)
    return {"wheel": str(wheel)}


def smoke(
    config: ResolvedConfig,
    *,
    verbose: bool = False,
    dry_run: bool = False,
    force: bool = False,
    require_wheel: bool = True,
) -> dict[str, Any]:
    wheel = latest_wheel(config, error_code=SMOKE_ERROR) if require_wheel else latest_wheel_optional(config)
    if not config.local.maya_py.exists():
        raise CliError(f"mayapy not found: {config.local.maya_py}", DEPENDENCY_ERROR)

    smoke_root = config.repo_root / "build" / "smoke"
    extract_dir = smoke_root / "wheel"
    deletion_targets = plan_smoke_cleanup(extract_dir)
    command = [str(config.local.maya_py), "-c", smoke_script(config)]
    details: dict[str, Any] = {
        "extract_dir": str(extract_dir),
        "wheel": str(wheel) if wheel else "after build step",
    }
    if dry_run:
        return render_dry_run("smoke", deletion_targets, command=command, details=details)

    require_confirmation(
        "smoke",
        deletion_targets,
        force=force,
    )
    delete_paths(deletion_targets)
    extract_dir.mkdir(parents=True, exist_ok=True)

    if wheel is None:
        raise CliError("No built wheel found for smoke step.", SMOKE_ERROR)

    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(extract_dir)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(extract_dir)
    result = run_command(command, cwd=config.repo_root, env=env, verbose=verbose, error_code=SMOKE_ERROR)
    output = result.stdout.strip()
    return {"wheel": str(wheel), "smoke_output": output.splitlines()}


def assemble(
    config: ResolvedConfig,
    *,
    module_name: str | None = None,
    maya_version: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    require_wheel: bool = True,
) -> dict[str, Any]:
    wheel = latest_wheel(config, error_code=ASSEMBLE_ERROR) if require_wheel else latest_wheel_optional(config)
    resolved_module = module_name or config.build.module_name
    resolved_maya_version = maya_version or config.build.maya_version
    module_root = config.repo_root / "dist" / "module" / resolved_module
    scripts_root = module_root / "contents" / "scripts"
    deletion_targets = plan_assemble_cleanup(module_root)
    details = {
        "module_root": str(module_root),
        "module_file": str(module_root / f"{resolved_module}.mod"),
        "wheel": str(wheel) if wheel else "after build step",
    }
    if dry_run:
        return render_dry_run("assemble", deletion_targets, details=details)

    require_confirmation(
        "assemble",
        deletion_targets,
        force=force,
    )
    delete_paths(deletion_targets)
    scripts_root.mkdir(parents=True, exist_ok=True)

    if wheel is None:
        raise CliError("No built wheel found for assemble step.", ASSEMBLE_ERROR)

    with zipfile.ZipFile(wheel) as archive:
        for member in archive.infolist():
            top = member.filename.split("/", 1)[0]
            if top.endswith(".dist-info") or top.endswith(".data"):
                continue
            archive.extract(member, scripts_root)

    mod_path = module_root / f"{resolved_module}.mod"
    mod_path.write_text(
        f"+ MAYAVERSION:{resolved_maya_version} PLATFORM:win64 {resolved_module} {config.build.version} .\\contents",
        encoding="utf-8",
    )
    return {"module_root": str(module_root), "module_file": str(mod_path)}


def run_pipeline(
    config: ResolvedConfig,
    *,
    verbose: bool = False,
    ensure_env: bool = False,
    skip_smoke: bool = False,
    skip_assemble: bool = False,
    module_name: str | None = None,
    maya_version: str | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    steps: dict[str, Any] = {}
    if dry_run:
        if ensure_env and not config.local.env_path.exists():
            steps["create_env"] = create_env(
                config,
                verbose=verbose,
                dry_run=True,
                force=force,
            )
        steps["build"] = build(
            config,
            verbose=verbose,
            dry_run=True,
            force=force,
        )
        if not skip_smoke:
            steps["smoke"] = smoke(
                config,
                verbose=verbose,
                dry_run=True,
                force=force,
                require_wheel=False,
            )
        if not skip_assemble:
            steps["assemble"] = assemble(
                config,
                module_name=module_name,
                maya_version=maya_version,
                dry_run=True,
                force=force,
                require_wheel=False,
            )
        return {"dry_run": True, "steps": steps}

    pipeline_deletions = plan_pipeline_cleanup(
        config,
        skip_smoke=skip_smoke,
        skip_assemble=skip_assemble,
        module_name=module_name,
    )
    require_confirmation(
        "run",
        pipeline_deletions,
        force=force,
    )

    if ensure_env and not config.local.env_path.exists():
        steps["create_env"] = create_env(
            config,
            verbose=verbose,
            force=True,
        )
    steps["build"] = build(
        config,
        verbose=verbose,
        force=True,
    )
    if not skip_smoke:
        steps["smoke"] = smoke(
            config,
            verbose=verbose,
            force=True,
        )
    if not skip_assemble:
        steps["assemble"] = assemble(
            config,
            module_name=module_name,
            maya_version=maya_version,
            force=True,
        )
    return steps


def probe_maya_runtime(maya_py: Path) -> dict[str, str | None]:
    if not maya_py.exists():
        return {"maya_py": str(maya_py), "include_dir": None, "lib_dir": None, "lib_name": None}

    maya_root = maya_py.parent.parent
    include_dir = maya_root / "Python" / "Include"
    if not include_dir.exists():
        headers = sorted(maya_root.rglob("Python.h"))
        include_dir = headers[0].parent if headers else None

    lib_dir = maya_root / "lib"
    lib_name = None
    if lib_dir.exists():
        libs = sorted(lib_dir.glob("python*.lib"))
        if libs:
            lib_name = libs[0].stem
    else:
        lib_dir = None

    return {
        "maya_py": str(maya_py),
        "include_dir": str(include_dir) if include_dir else None,
        "lib_dir": str(lib_dir) if lib_dir else None,
        "lib_name": lib_name,
    }


def plan_create_env_refresh(config: ResolvedConfig) -> list[DeletionTarget]:
    if not config.local.env_path.exists():
        return []
    return [DeletionTarget(config.local.env_path, "replace existing Conda environment")]


def plan_build_cleanup(repo_root: Path) -> list[DeletionTarget]:
    deletion_targets: list[DeletionTarget] = []
    build_root = repo_root / "build"
    if build_root.exists():
        for pattern in ("lib.*", "bdist.*", "temp.*", "cython", "target-build", "tmp"):
            for path in sorted(build_root.glob(pattern)):
                deletion_targets.append(DeletionTarget(path, f"clean build artifact matching {pattern}"))
    for egg_info in sorted(repo_root.glob("*.egg-info")):
        if egg_info.is_dir():
            deletion_targets.append(DeletionTarget(egg_info, "remove stale egg-info metadata"))
    return deletion_targets


def plan_smoke_cleanup(extract_dir: Path) -> list[DeletionTarget]:
    if not extract_dir.exists():
        return []
    return [DeletionTarget(extract_dir, "replace previous smoke extraction")]


def plan_assemble_cleanup(module_root: Path) -> list[DeletionTarget]:
    if not module_root.exists():
        return []
    return [DeletionTarget(module_root, "replace previous assembled module output")]


def plan_pipeline_cleanup(
    config: ResolvedConfig,
    *,
    skip_smoke: bool,
    skip_assemble: bool,
    module_name: str | None,
) -> list[DeletionTarget]:
    deletion_targets = plan_build_cleanup(config.repo_root)
    if not skip_smoke:
        deletion_targets.extend(plan_smoke_cleanup(config.repo_root / "build" / "smoke" / "wheel"))
    if not skip_assemble:
        resolved_module = module_name or config.build.module_name
        deletion_targets.extend(
            plan_assemble_cleanup(config.repo_root / "dist" / "module" / resolved_module)
        )
    return deletion_targets


def delete_paths(paths: list[DeletionTarget]) -> None:
    for target in paths:
        if target.path.is_dir():
            shutil.rmtree(target.path)
        elif target.path.exists():
            target.path.unlink()


def require_confirmation(
    command_name: str,
    deletion_targets: list[DeletionTarget],
    *,
    force: bool,
) -> None:
    if not deletion_targets or force:
        return

    raise CliError(
        (
            f"{command_name} would delete existing outputs. "
            "Run with --dry-run to inspect the plan, then re-run with --force to allow deletion."
        ),
        USAGE_ERROR,
    )


def render_dry_run(
    command_name: str,
    deletion_targets: list[DeletionTarget],
    *,
    command: list[str] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "dry_run": True,
        "command": command_name,
        "delete": [{"path": str(target.path), "reason": target.reason} for target in deletion_targets],
    }
    if command is not None:
        payload["would_run"] = command
    if details:
        payload.update(details)
    return payload


def latest_wheel_optional(config: ResolvedConfig) -> Path | None:
    try:
        return latest_wheel(config)
    except CliError:
        return None


def latest_wheel(config: ResolvedConfig, *, error_code: int = BUILD_ERROR) -> Path:
    dist_dir = config.repo_root / "dist"
    distribution = config.build.distribution_name.replace("-", "_")
    wheels = sorted(
        dist_dir.glob(f"{distribution}-*.whl"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not wheels:
        raise CliError(f"No built wheel found in {dist_dir}", error_code)
    return wheels[0]


def smoke_script(config: ResolvedConfig) -> str:
    lines = [
        "import importlib",
        "from importlib import resources",
        "",
        f"importlib.import_module({config.build.package_name!r})",
    ]
    for module_name in config.build.smoke.compiled_modules:
        lines.append(f"importlib.import_module({f'{config.build.package_name}.{module_name}'!r})")
    if config.build.smoke.callable:
        lines.extend(
            [
                "",
                f"package = importlib.import_module({config.build.package_name!r})",
                f"print(getattr(package, {config.build.smoke.callable!r})())",
            ]
        )
    if config.build.smoke.resource_check:
        lines.extend(
            [
                "",
                f"package_files = resources.files({config.build.package_name!r})",
                (
                    "print("
                    f"package_files.joinpath({config.build.smoke.resource_check!r}).is_file()"
                    ")"
                ),
            ]
        )
    return "\n".join(lines)


def run_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    verbose: bool = False,
    error_code: int,
) -> subprocess.CompletedProcess[str]:
    if verbose:
        print(f"$ {' '.join(command)}", file=sys.stderr)

    result = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if is_interrupt_returncode(result.returncode):
        raise CliError("Interrupted.", INTERRUPTED_ERROR)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Command failed."
        raise CliError(message, error_code)
    return result


def is_interrupt_returncode(returncode: int) -> bool:
    return returncode in {
        130,
        -2,
        -1073741510,
        0xC000013A,
    }
