from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import ResolvedConfig
from .errors import BUILD_ERROR, USAGE_ERROR, CliError
from .filesystem import ensure_path_within_directory

ARTIFACT_MANIFEST_FILENAME = "artifact.json"
RELEASE_INSTALL_FILENAME = "INSTALL.txt"


@dataclass(frozen=True, slots=True)
class DeletionTarget:
    path: Path
    reason: str
    root: Path | None = None


def plan_create_env_refresh(config: ResolvedConfig) -> list[DeletionTarget]:
    if not config.local.env_path.exists():
        return []
    return [DeletionTarget(config.local.env_path, "replace existing Conda environment", config.local.env_path)]


def plan_build_cleanup(config: ResolvedConfig) -> list[DeletionTarget]:
    deletion_targets: list[DeletionTarget] = []
    for path, reason in (
        (
            config.repo_root / "build" / "target-build" / config.build.target_name,
            f"replace generated build tree for target {config.build.target_name}",
        ),
        (
            target_temp_root(config),
            f"replace build temp files for target {config.build.target_name}",
        ),
        (
            target_dist_dir(config),
            f"replace wheel output for target {config.build.target_name}",
        ),
    ):
        if path.exists():
            deletion_targets.append(DeletionTarget(path, reason, config.repo_root))
    for egg_info in sorted(config.repo_root.glob("*.egg-info")):
        if egg_info.is_dir():
            deletion_targets.append(DeletionTarget(egg_info, "remove stale egg-info metadata", config.repo_root))
    return deletion_targets


def plan_smoke_cleanup(extract_dir: Path) -> list[DeletionTarget]:
    if not extract_dir.exists():
        return []
    return [DeletionTarget(extract_dir, "replace previous smoke extraction", extract_dir)]


def plan_assemble_cleanup(module_root: Path) -> list[DeletionTarget]:
    if not module_root.exists():
        return []
    return [DeletionTarget(module_root, "replace previous assembled module output", module_root)]


def plan_package_cleanup(release_dir: Path) -> list[DeletionTarget]:
    if not release_dir.exists():
        return []
    return [DeletionTarget(release_dir, "replace previous release package output", release_dir)]


def plan_pipeline_cleanup(
    config: ResolvedConfig,
    *,
    skip_smoke: bool,
    skip_assemble: bool,
    skip_package: bool,
) -> list[DeletionTarget]:
    deletion_targets = plan_build_cleanup(config)
    if not skip_smoke:
        deletion_targets.extend(plan_smoke_cleanup(target_smoke_extract_dir(config)))
    if not skip_assemble:
        deletion_targets.extend(plan_assemble_cleanup(target_module_root(config)))
    if not skip_package:
        deletion_targets.extend(plan_package_cleanup(target_release_dir(config)))
    return deletion_targets


def target_temp_root(config: ResolvedConfig) -> Path:
    return config.repo_root / "build" / "tmp" / config.build.target_name


def target_env_spec_path(config: ResolvedConfig) -> Path:
    return target_temp_root(config) / "conda-environment.yml"


def target_dist_dir(config: ResolvedConfig) -> Path:
    return config.repo_root / "dist" / config.build.target_name


def target_artifact_manifest_path(config: ResolvedConfig) -> Path:
    return target_dist_dir(config) / ARTIFACT_MANIFEST_FILENAME


def target_smoke_extract_dir(config: ResolvedConfig) -> Path:
    return config.repo_root / "build" / "smoke" / config.build.target_name / "wheel"


def target_module_root(config: ResolvedConfig) -> Path:
    return config.repo_root / "dist" / "module" / config.build.target_name / config.build.module_name


def target_release_dir(config: ResolvedConfig) -> Path:
    return config.repo_root / "dist" / "release" / config.build.target_name


def release_archive_basename(config: ResolvedConfig) -> str:
    return (
        f"{config.build.module_name}-{config.build.version}-"
        f"maya{config.build.maya_version}-{config.build.platform}"
    )


def target_release_archive_path(config: ResolvedConfig) -> Path:
    return target_release_dir(config) / f"{release_archive_basename(config)}.zip"


def render_module_definition(config: ResolvedConfig) -> str:
    return (
        f"+ MAYAVERSION:{config.build.maya_version} "
        f"PLATFORM:{module_platform_token(config.build.platform)} "
        f"{config.build.module_name} {config.build.version} {module_contents_root(config.build.platform)}"
    )


def render_release_install_text(config: ResolvedConfig) -> str:
    return (
        f"{config.build.module_name} {config.build.version}\n"
        f"Target: {config.build.target_name}\n"
        f"Maya: {config.build.maya_version}\n"
        f"Platform: {config.build.platform}\n"
        "\n"
        "Install:\n"
        "1. Extract this zip to a folder that Maya scans through MAYA_MODULE_PATH.\n"
        f"2. Keep the top-level folder named {config.build.module_name} intact.\n"
        "3. Start Maya.\n"
        "\n"
        "Python usage:\n"
        f"import {config.build.package_name}\n"
        f"{config.build.package_name}.show_ui()\n"
    )


def module_contents_root(platform: str) -> str:
    return ".\\contents" if platform == "windows" else "./contents"


def module_platform_token(platform: str) -> str:
    return {
        "windows": "win64",
        "linux": "linux",
        "macos": "mac",
    }[platform]


def render_target_environment_yaml(base_environment: str, python_version: str) -> str:
    lines = base_environment.splitlines()
    rendered_line = f"  - python={python_version}"
    replaced = False
    for index, line in enumerate(lines):
        if re.match(r"^\s*-\s*python\b.*$", line):
            lines[index] = rendered_line
            replaced = True
            break
    if not replaced:
        try:
            dependencies_index = next(index for index, line in enumerate(lines) if line.strip() == "dependencies:")
        except StopIteration:
            lines.extend(["dependencies:", rendered_line])
        else:
            lines.insert(dependencies_index + 1, rendered_line)
    return "\n".join(lines) + "\n"


def write_target_environment_file(config: ResolvedConfig, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    base_environment = (config.repo_root / "environment.yml").read_text(encoding="utf-8")
    destination.write_text(
        render_target_environment_yaml(base_environment, config.build.python_version),
        encoding="utf-8",
    )


def delete_paths(paths: list[DeletionTarget]) -> None:
    for target in paths:
        if target.root is not None:
            ensure_path_within_directory(
                target.path,
                target.root,
                subject=f"Deletion target {target.path}",
                error_code=USAGE_ERROR,
            )
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
    from .artifacts import latest_artifact_optional

    artifact = latest_artifact_optional(config, error_code=BUILD_ERROR)
    return artifact.wheel if artifact else None


def latest_wheel(config: ResolvedConfig, *, error_code: int = BUILD_ERROR) -> Path:
    from .artifacts import resolve_built_artifact

    return resolve_built_artifact(config, error_code=error_code).wheel
