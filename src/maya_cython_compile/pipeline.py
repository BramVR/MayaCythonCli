from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

from .artifacts import (
    BuiltArtifact,
    artifact_metadata_member,
    candidate_wheels,
    expected_artifact_metadata,
    file_sha256,
    latest_artifact_optional,
    latest_wheel,
    latest_wheel_optional,
    load_artifact_manifest,
    load_wheel_artifact_metadata,
    resolve_built_artifact,
    validate_artifact_metadata,
    write_artifact_manifest,
)
from .conda import conda_command, conda_executable_exists
from .config import ResolvedConfig, as_dict
from .errors import (
    ASSEMBLE_ERROR,
    BUILD_ERROR,
    DEPENDENCY_ERROR,
    INTERRUPTED_ERROR,
    PACKAGE_ERROR,
    SMOKE_ERROR,
    CliError,
)
from .filesystem import safe_extract_all, safe_extract_member
from .paths import (
    ARTIFACT_MANIFEST_FILENAME,
    RELEASE_INSTALL_FILENAME,
    DeletionTarget,
    delete_paths,
    module_contents_root,
    module_platform_token,
    plan_assemble_cleanup,
    plan_build_cleanup,
    plan_create_env_refresh,
    plan_package_cleanup,
    plan_pipeline_cleanup,
    plan_smoke_cleanup,
    release_archive_basename,
    render_dry_run,
    render_module_definition,
    render_release_install_text,
    render_target_environment_yaml,
    require_confirmation,
    target_artifact_manifest_path,
    target_dist_dir,
    target_env_spec_path,
    target_module_root,
    target_release_archive_path,
    target_release_dir,
    target_smoke_extract_dir,
    target_temp_root,
    write_target_environment_file,
)
from .runtime_probe import (
    MayaRuntimeProbe,
    ensure_maya_build_runtime,
    is_interrupt_returncode,
    normalized_python_version,
    probe_maya_runtime,
    python_version_matches_target,
)
from .target_builder import ARTIFACT_METADATA_FILENAME, prepare_build_tree, render_artifact_metadata

__all__ = [
    "ARTIFACT_MANIFEST_FILENAME",
    "ARTIFACT_METADATA_FILENAME",
    "BuiltArtifact",
    "DeletionTarget",
    "MayaRuntimeProbe",
    "artifact_metadata_member",
    "assemble",
    "build",
    "candidate_wheels",
    "conda_command",
    "create_env",
    "delete_paths",
    "doctor",
    "ensure_maya_build_runtime",
    "expected_artifact_metadata",
    "file_sha256",
    "is_interrupt_returncode",
    "latest_artifact_optional",
    "latest_wheel",
    "latest_wheel_optional",
    "load_artifact_manifest",
    "load_wheel_artifact_metadata",
    "module_contents_root",
    "module_platform_token",
    "normalized_python_version",
    "package",
    "plan_assemble_cleanup",
    "plan_build_cleanup",
    "plan_create_env_refresh",
    "plan_package_cleanup",
    "plan_pipeline_cleanup",
    "plan_smoke_cleanup",
    "probe_maya_runtime",
    "python_version_matches_target",
    "release_archive_basename",
    "render_artifact_metadata",
    "render_dry_run",
    "render_module_definition",
    "render_release_install_text",
    "render_target_environment_yaml",
    "require_confirmation",
    "resolve_built_artifact",
    "run_command",
    "run_pipeline",
    "show_config",
    "smoke",
    "smoke_script",
    "target_artifact_manifest_path",
    "target_dist_dir",
    "target_env_spec_path",
    "target_module_root",
    "target_release_archive_path",
    "target_release_dir",
    "target_smoke_extract_dir",
    "target_temp_root",
    "validate_artifact_metadata",
    "write_artifact_manifest",
    "write_target_environment_file",
]


def show_config(config: ResolvedConfig) -> dict[str, Any]:
    return as_dict(config)


def doctor(config: ResolvedConfig) -> dict[str, Any]:
    maya = probe_maya_runtime(
        config.local.maya_py,
        target_platform=config.build.platform,
        target_python_version=config.build.python_version,
    )
    return {
        "config": show_config(config),
        "checks": {
            "conda_exe_exists": conda_executable_exists(config.local.conda_exe),
            "env_exists": config.local.env_path.exists(),
            "maya_py_exists": config.local.maya_py.exists(),
            "maya_probe_ok": maya.probe_succeeded,
            "maya_platform_matches_target": maya.doctor_platform_check(),
            "maya_python_matches_target": maya.doctor_python_check(),
            "maya_include_exists": maya.include_dir is not None,
            "maya_lib_exists": maya.library_file is not None,
        },
        "maya_runtime": maya.as_dict(),
    }


def create_env(
    config: ResolvedConfig,
    *,
    verbose: bool = False,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    if not conda_executable_exists(config.local.conda_exe):
        raise CliError(f"Conda was not found at {config.local.conda_exe}", DEPENDENCY_ERROR)

    deletion_targets = plan_create_env_refresh(config)
    environment_file = target_env_spec_path(config)
    command = conda_command(
        config.local.conda_exe,
        "env",
        "create",
        "--prefix",
        str(config.local.env_path),
    )
    if deletion_targets:
        command.append("--force")
    command.extend(["--file", str(environment_file)])

    if dry_run:
        return render_dry_run(
            "create-env",
            deletion_targets,
            command=command,
            details={
                "target": config.build.target_name,
                "env_path": str(config.local.env_path),
                "python_version": config.build.python_version,
                "environment_file": str(environment_file),
            },
        )

    require_confirmation(
        "create-env",
        deletion_targets,
        force=force,
    )
    write_target_environment_file(config, environment_file)
    run_command(command, cwd=config.repo_root, verbose=verbose, error_code=DEPENDENCY_ERROR)
    return {"env_path": str(config.local.env_path)}


def build(
    config: ResolvedConfig,
    *,
    verbose: bool = False,
    dry_run: bool = False,
    force: bool = False,
    require_env: bool = True,
) -> dict[str, Any]:
    if require_env and not config.local.env_path.exists():
        raise CliError(
            f"Conda environment missing: {config.local.env_path}. Run create-env first.",
            DEPENDENCY_ERROR,
        )

    maya = probe_maya_runtime(
        config.local.maya_py,
        target_platform=config.build.platform,
        target_python_version=config.build.python_version,
    )
    ensure_maya_build_runtime(maya, config.local.maya_py)

    deletion_targets = plan_build_cleanup(config)
    dist_dir = target_dist_dir(config)
    command = conda_command(
        config.local.conda_exe,
        "run",
        "--prefix",
        str(config.local.env_path),
        "python",
        "-m",
        "build",
        "--wheel",
        "--no-isolation",
        "--outdir",
        str(dist_dir),
    )
    if dry_run:
        return render_dry_run(
            "build",
            deletion_targets,
            command=command,
            details={
                "target": config.build.target_name,
                "dist_dir": str(dist_dir),
                "artifact_manifest": str(target_artifact_manifest_path(config)),
            },
        )

    require_confirmation(
        "build",
        deletion_targets,
        force=force,
    )
    delete_paths(deletion_targets)
    build_tree = prepare_build_tree(config)
    dist_dir.mkdir(parents=True, exist_ok=True)

    temp_root = target_temp_root(config)
    temp_root.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(maya.build_env())
    env["TEMP"] = str(temp_root)
    env["TMP"] = str(temp_root)

    run_command(command, cwd=build_tree, env=env, verbose=verbose, error_code=BUILD_ERROR)
    artifact = resolve_built_artifact(config, error_code=BUILD_ERROR, require_manifest=False, require_unique=True)
    write_artifact_manifest(config, artifact.wheel, artifact.metadata)
    return {"wheel": str(artifact.wheel), "artifact_manifest": str(target_artifact_manifest_path(config))}


def smoke(
    config: ResolvedConfig,
    *,
    verbose: bool = False,
    dry_run: bool = False,
    force: bool = False,
    require_wheel: bool = True,
) -> dict[str, Any]:
    artifact = (
        resolve_built_artifact(config, error_code=SMOKE_ERROR)
        if require_wheel
        else latest_artifact_optional(config, error_code=SMOKE_ERROR)
    )
    wheel = artifact.wheel if artifact else None
    if not config.local.maya_py.exists():
        raise CliError(f"mayapy not found: {config.local.maya_py}", DEPENDENCY_ERROR)

    extract_dir = target_smoke_extract_dir(config)
    deletion_targets = plan_smoke_cleanup(extract_dir)
    command = [str(config.local.maya_py), "-c", smoke_script(config)]
    details: dict[str, Any] = {
        "target": config.build.target_name,
        "extract_dir": str(extract_dir),
        "wheel": str(wheel) if wheel else "after build step",
        "artifact_manifest": str(target_artifact_manifest_path(config)),
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
        safe_extract_all(archive, extract_dir, error_code=SMOKE_ERROR)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(extract_dir)
    result = run_command(command, cwd=config.repo_root, env=env, verbose=verbose, error_code=SMOKE_ERROR)
    output = result.stdout.strip()
    return {
        "wheel": str(wheel),
        "artifact_manifest": str(target_artifact_manifest_path(config)),
        "smoke_output": output.splitlines(),
    }


def assemble(
    config: ResolvedConfig,
    *,
    dry_run: bool = False,
    force: bool = False,
    require_wheel: bool = True,
) -> dict[str, Any]:
    artifact = (
        resolve_built_artifact(config, error_code=ASSEMBLE_ERROR)
        if require_wheel
        else latest_artifact_optional(config, error_code=ASSEMBLE_ERROR)
    )
    wheel = artifact.wheel if artifact else None
    module_root = target_module_root(config)
    scripts_root = module_root / "contents" / "scripts"
    mod_path = module_root / f"{config.build.module_name}.mod"
    deletion_targets = plan_assemble_cleanup(module_root)
    details = {
        "target": config.build.target_name,
        "target_platform": config.build.platform,
        "target_maya_version": config.build.maya_version,
        "module_root": str(module_root),
        "module_file": str(mod_path),
        "wheel": str(wheel) if wheel else "after build step",
        "artifact_manifest": str(target_artifact_manifest_path(config)),
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
            safe_extract_member(archive, member, scripts_root, error_code=ASSEMBLE_ERROR)

    mod_path.write_text(render_module_definition(config), encoding="utf-8")
    return {
        "wheel": str(wheel),
        "artifact_manifest": str(target_artifact_manifest_path(config)),
        "module_root": str(module_root),
        "module_file": str(mod_path),
    }


def package(
    config: ResolvedConfig,
    *,
    dry_run: bool = False,
    force: bool = False,
    require_module: bool = True,
) -> dict[str, Any]:
    module_root = target_module_root(config)
    archive_path = target_release_archive_path(config)
    release_dir = target_release_dir(config)
    deletion_targets = plan_package_cleanup(release_dir)
    details = {
        "target": config.build.target_name,
        "module_root": str(module_root) if module_root.exists() or require_module else "after assemble step",
        "release_dir": str(release_dir),
        "archive": str(archive_path),
        "artifact_manifest": str(target_artifact_manifest_path(config)),
    }
    if dry_run:
        return render_dry_run("package", deletion_targets, details=details)

    require_confirmation(
        "package",
        deletion_targets,
        force=force,
    )
    delete_paths(deletion_targets)
    release_dir.mkdir(parents=True, exist_ok=True)

    if not module_root.exists():
        if require_module:
            raise CliError(
                (
                    f"No assembled Maya module found at {module_root}. "
                    f"Run assemble again for target {config.build.target_name}."
                ),
                PACKAGE_ERROR,
            )
        raise CliError("No assembled Maya module found for package step.", PACKAGE_ERROR)

    install_text = render_release_install_text(config)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{config.build.module_name}/{RELEASE_INSTALL_FILENAME}", install_text)
        for path in sorted(module_root.rglob("*")):
            if path.is_dir():
                continue
            archive.write(path, arcname=(Path(config.build.module_name) / path.relative_to(module_root)).as_posix())

    return {
        "artifact_manifest": str(target_artifact_manifest_path(config)),
        "module_root": str(module_root),
        "release_dir": str(release_dir),
        "archive": str(archive_path),
    }


def run_pipeline(
    config: ResolvedConfig,
    *,
    verbose: bool = False,
    ensure_env: bool = False,
    skip_smoke: bool = False,
    skip_assemble: bool = False,
    skip_package: bool = False,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    steps: dict[str, Any] = {}
    env_missing = not config.local.env_path.exists()
    if dry_run:
        if ensure_env and env_missing:
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
            require_env=not (ensure_env and env_missing),
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
                dry_run=True,
                force=force,
                require_wheel=False,
            )
        if not skip_package:
            steps["package"] = package(
                config,
                dry_run=True,
                force=force,
                require_module=skip_assemble,
            )
        return {"dry_run": True, "steps": steps}

    pipeline_deletions = plan_pipeline_cleanup(
        config,
        skip_smoke=skip_smoke,
        skip_assemble=skip_assemble,
        skip_package=skip_package,
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
            force=True,
        )
    if not skip_package:
        steps["package"] = package(
            config,
            force=True,
            require_module=not skip_assemble,
        )
    return steps


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
