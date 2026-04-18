from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .conda import conda_command, conda_executable_exists
from .config import ResolvedConfig, as_dict
from .errors import (
    ASSEMBLE_ERROR,
    BUILD_ERROR,
    DEPENDENCY_ERROR,
    INTERRUPTED_ERROR,
    SMOKE_ERROR,
    USAGE_ERROR,
    CliError,
)
from .target_builder import ARTIFACT_METADATA_FILENAME, prepare_build_tree, render_artifact_metadata


@dataclass(frozen=True, slots=True)
class DeletionTarget:
    path: Path
    reason: str


@dataclass(frozen=True, slots=True)
class MayaRuntimeProbe:
    maya_py: str
    probe_succeeded: bool
    error: str | None = None
    target_platform: str | None = None
    target_python_version: str | None = None
    runtime_platform: str | None = None
    platform_matches_target: bool | None = None
    python_executable: str | None = None
    python_version: str | None = None
    python_matches_target: bool | None = None
    python_prefix: str | None = None
    python_base_prefix: str | None = None
    sys_platform: str | None = None
    sysconfig_platform: str | None = None
    include_dir: str | None = None
    platinclude_dir: str | None = None
    library_dir: str | None = None
    library_name: str | None = None
    library_file: str | None = None
    extension_suffix: str | None = None
    soabi: str | None = None
    config_vars: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def doctor_platform_check(self) -> bool:
        return self.platform_matches_target is True if self.target_platform else self.probe_succeeded

    def doctor_python_check(self) -> bool:
        return self.python_matches_target is True if self.target_python_version else self.probe_succeeded

    def build_env(self) -> dict[str, str]:
        return {
            "MAYA_PYTHON_INCLUDE": self.include_dir or "",
            "MAYA_PYTHON_LIBDIR": self.library_dir or "",
            "MAYA_PYTHON_LIBNAME": self.library_name or "",
            "MAYA_PYTHON_LIBRARYFILE": self.library_file or "",
            "MAYA_RUNTIME_PLATFORM": self.runtime_platform or "",
            "MAYA_TARGET_PLATFORM": self.target_platform or "",
            "MAYA_PYTHON_VERSION": self.python_version or "",
            "MAYA_PYTHON_EXT_SUFFIX": self.extension_suffix or "",
            "MAYA_PYTHON_SOABI": self.soabi or "",
        }


@dataclass(frozen=True, slots=True)
class BuiltArtifact:
    wheel: Path
    manifest_path: Path | None
    sha256: str
    metadata: dict[str, Any]


MAYA_RUNTIME_PROBE_SCRIPT = """
import json
import sys
import sysconfig


def _runtime_platform() -> str:
    return {
        "win32": "windows",
        "cygwin": "windows",
        "linux": "linux",
        "darwin": "macos",
    }.get(sys.platform, sys.platform)


payload = {
    "maya_py": sys.executable,
    "runtime_platform": _runtime_platform(),
    "sys_platform": sys.platform,
    "sysconfig_platform": sysconfig.get_platform(),
    "python_version": ".".join(str(part) for part in sys.version_info[:3]),
    "python_prefix": sys.prefix,
    "python_base_prefix": sys.base_prefix,
    "include_dir": sysconfig.get_path("include"),
    "platinclude_dir": sysconfig.get_path("platinclude"),
    "config_vars": {
        key: sysconfig.get_config_var(key)
        for key in (
            "INCLUDEPY",
            "CONFINCLUDEPY",
            "LIBDIR",
            "LIBPL",
            "LIBRARY",
            "LDLIBRARY",
            "INSTSONAME",
            "EXT_SUFFIX",
            "SOABI",
        )
    },
}
print(json.dumps(payload))
""".strip()
ARTIFACT_MANIFEST_FILENAME = "artifact.json"


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
) -> dict[str, Any]:
    if not config.local.env_path.exists():
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
        "setup.py",
        "bdist_wheel",
        "--dist-dir",
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
        archive.extractall(extract_dir)

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
            archive.extract(member, scripts_root)

    mod_path.write_text(render_module_definition(config), encoding="utf-8")
    return {
        "wheel": str(wheel),
        "artifact_manifest": str(target_artifact_manifest_path(config)),
        "module_root": str(module_root),
        "module_file": str(mod_path),
    }


def run_pipeline(
    config: ResolvedConfig,
    *,
    verbose: bool = False,
    ensure_env: bool = False,
    skip_smoke: bool = False,
    skip_assemble: bool = False,
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
                dry_run=True,
                force=force,
                require_wheel=False,
            )
        return {"dry_run": True, "steps": steps}

    pipeline_deletions = plan_pipeline_cleanup(
        config,
        skip_smoke=skip_smoke,
        skip_assemble=skip_assemble,
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
    return steps


def probe_maya_runtime(
    maya_py: Path,
    *,
    target_platform: str | None = None,
    target_python_version: str | None = None,
) -> MayaRuntimeProbe:
    if not maya_py.exists():
        return _runtime_probe_result(
            maya_py=maya_py,
            target_platform=target_platform,
            target_python_version=target_python_version,
            error=f"mayapy not found: {maya_py}",
        )

    result = subprocess.run(
        [str(maya_py), "-c", MAYA_RUNTIME_PROBE_SCRIPT],
        capture_output=True,
        text=True,
        check=False,
    )
    if is_interrupt_returncode(result.returncode):
        raise CliError("Interrupted.", INTERRUPTED_ERROR)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "mayapy probe failed."
        return _runtime_probe_result(
            maya_py=maya_py,
            target_platform=target_platform,
            target_python_version=target_python_version,
            error=message,
        )

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return _runtime_probe_result(
            maya_py=maya_py,
            target_platform=target_platform,
            target_python_version=target_python_version,
            error=f"mayapy probe returned invalid JSON: {exc}",
        )

    runtime_platform = payload.get("runtime_platform")
    python_version = payload.get("python_version")
    config_vars = payload.get("config_vars", {})
    include_dir = _resolve_existing_path(
        payload.get("include_dir"),
        payload.get("platinclude_dir"),
        config_vars.get("INCLUDEPY"),
        config_vars.get("CONFINCLUDEPY"),
    )
    library_file = _resolve_python_library_file(config_vars)
    library_dir = str(library_file.parent) if library_file else None
    library_name = _library_name_from_filename(library_file.name) if library_file else None
    platform_matches_target = None
    if target_platform and runtime_platform:
        platform_matches_target = runtime_platform == target_platform
    python_matches_target = None
    if target_python_version and python_version:
        python_matches_target = python_version_matches_target(python_version, target_python_version)

    return MayaRuntimeProbe(
        maya_py=str(maya_py),
        probe_succeeded=True,
        target_platform=target_platform,
        target_python_version=target_python_version,
        runtime_platform=runtime_platform,
        platform_matches_target=platform_matches_target,
        python_executable=payload.get("maya_py"),
        python_version=python_version,
        python_matches_target=python_matches_target,
        python_prefix=payload.get("python_prefix"),
        python_base_prefix=payload.get("python_base_prefix"),
        sys_platform=payload.get("sys_platform"),
        sysconfig_platform=payload.get("sysconfig_platform"),
        include_dir=str(include_dir) if include_dir else None,
        platinclude_dir=payload.get("platinclude_dir"),
        library_dir=library_dir,
        library_name=library_name,
        library_file=str(library_file) if library_file else None,
        extension_suffix=config_vars.get("EXT_SUFFIX"),
        soabi=config_vars.get("SOABI"),
        config_vars={
            key: value
            for key, value in config_vars.items()
            if key in {"INCLUDEPY", "CONFINCLUDEPY", "LIBDIR", "LIBPL", "LIBRARY", "LDLIBRARY", "INSTSONAME"}
        },
    )


def ensure_maya_build_runtime(maya: MayaRuntimeProbe, maya_py: Path) -> None:
    if not maya.probe_succeeded:
        message = maya.error or f"Could not probe Maya Python runtime from {maya_py}"
        raise CliError(message, DEPENDENCY_ERROR)
    if maya.platform_matches_target is False:
        raise CliError(
            (
                f"Configured target platform {maya.target_platform} does not match "
                f"mayapy runtime {maya.runtime_platform}: {maya_py}"
            ),
            DEPENDENCY_ERROR,
        )
    if maya.python_matches_target is False:
        raise CliError(
            (
                f"Configured target Python {maya.target_python_version} does not match "
                f"mayapy runtime {maya.python_version}: {maya_py}"
            ),
            DEPENDENCY_ERROR,
        )
    if not maya.include_dir or not maya.library_dir or not maya.library_name or not maya.library_file:
        raise CliError(f"Could not resolve Maya Python runtime from {maya_py}", DEPENDENCY_ERROR)


def _runtime_probe_result(
    *,
    maya_py: Path,
    target_platform: str | None,
    target_python_version: str | None,
    error: str,
) -> MayaRuntimeProbe:
    return MayaRuntimeProbe(
        maya_py=str(maya_py),
        probe_succeeded=False,
        error=error,
        target_platform=target_platform,
        target_python_version=target_python_version,
    )


def _resolve_existing_path(*raw_paths: str | None) -> Path | None:
    for raw_path in raw_paths:
        if not raw_path:
            continue
        path = Path(raw_path)
        if path.exists():
            return path
    return None


def _resolve_python_library_file(config_vars: dict[str, Any]) -> Path | None:
    candidate_names: list[str] = []
    for key in ("LIBRARY", "LDLIBRARY", "INSTSONAME"):
        raw_value = config_vars.get(key)
        if not raw_value or not isinstance(raw_value, str):
            continue
        path = Path(raw_value)
        if path.is_absolute() and path.exists():
            return path
        candidate_names.append(path.name)

    candidate_dirs: list[Path] = []
    for key in ("LIBDIR", "LIBPL"):
        raw_value = config_vars.get(key)
        if not raw_value or not isinstance(raw_value, str):
            continue
        path = Path(raw_value)
        if path.exists():
            candidate_dirs.append(path)

    seen: set[Path] = set()
    unique_dirs: list[Path] = []
    for candidate_dir in candidate_dirs:
        resolved = candidate_dir.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_dirs.append(candidate_dir)

    for candidate_dir in unique_dirs:
        for candidate_name in candidate_names:
            candidate_file = candidate_dir / candidate_name
            if candidate_file.exists():
                return candidate_file
    return None


def _library_name_from_filename(filename: str) -> str:
    normalized = filename
    for suffix in (".lib", ".dll", ".dylib", ".a", ".so"):
        marker = normalized.lower().find(suffix)
        if marker != -1:
            normalized = normalized[:marker]
            break
    if normalized.startswith("lib") and not filename.lower().endswith(".lib"):
        normalized = normalized[3:]
    return normalized


def plan_create_env_refresh(config: ResolvedConfig) -> list[DeletionTarget]:
    if not config.local.env_path.exists():
        return []
    return [DeletionTarget(config.local.env_path, "replace existing Conda environment")]


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
            deletion_targets.append(DeletionTarget(path, reason))
    for egg_info in sorted(config.repo_root.glob("*.egg-info")):
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
) -> list[DeletionTarget]:
    deletion_targets = plan_build_cleanup(config)
    if not skip_smoke:
        deletion_targets.extend(plan_smoke_cleanup(target_smoke_extract_dir(config)))
    if not skip_assemble:
        deletion_targets.extend(plan_assemble_cleanup(target_module_root(config)))
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


def render_module_definition(config: ResolvedConfig) -> str:
    return (
        f"+ MAYAVERSION:{config.build.maya_version} "
        f"PLATFORM:{module_platform_token(config.build.platform)} "
        f"{config.build.module_name} {config.build.version} {module_contents_root(config.build.platform)}"
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


def python_version_matches_target(runtime_version: str, target_version: str) -> bool:
    runtime_parts = normalized_python_version(runtime_version)
    target_parts = normalized_python_version(target_version)
    if not runtime_parts or not target_parts:
        return runtime_version == target_version
    return runtime_parts[: len(target_parts)] == target_parts


def normalized_python_version(raw_value: str) -> tuple[int, ...]:
    match = re.match(r"^\s*(\d+(?:\.\d+)*)", raw_value)
    if match is None:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


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


def latest_artifact_optional(config: ResolvedConfig, *, error_code: int) -> BuiltArtifact | None:
    try:
        return resolve_built_artifact(config, error_code=error_code)
    except CliError:
        return None


def latest_wheel_optional(config: ResolvedConfig) -> Path | None:
    artifact = latest_artifact_optional(config, error_code=BUILD_ERROR)
    return artifact.wheel if artifact else None


def latest_wheel(config: ResolvedConfig, *, error_code: int = BUILD_ERROR) -> Path:
    return resolve_built_artifact(config, error_code=error_code).wheel


def resolve_built_artifact(
    config: ResolvedConfig,
    *,
    error_code: int,
    require_manifest: bool = True,
    require_unique: bool = False,
) -> BuiltArtifact:
    manifest_path = target_artifact_manifest_path(config)
    if manifest_path.exists():
        manifest = load_artifact_manifest(config, error_code=error_code)
        wheel_name = manifest.get("wheel")
        if not isinstance(wheel_name, str) or not wheel_name:
            raise CliError(f"Invalid artifact manifest at {manifest_path}", error_code)
        wheel = target_dist_dir(config) / wheel_name
        if not wheel.exists():
            raise CliError(f"Artifact manifest points to a missing wheel: {wheel}", error_code)
        expected_sha256 = manifest.get("sha256")
        if not isinstance(expected_sha256, str) or not expected_sha256:
            raise CliError(f"Invalid artifact manifest at {manifest_path}", error_code)
        actual_sha256 = file_sha256(wheel)
        if actual_sha256 != expected_sha256:
            raise CliError(
                (
                    f"Artifact manifest {manifest_path} does not match wheel contents for {wheel}: "
                    f"sha256={actual_sha256} expected {expected_sha256}"
                ),
                error_code,
            )
        metadata = load_wheel_artifact_metadata(wheel, error_code=error_code)
        validate_artifact_metadata(
            manifest.get("build"),
            expected_artifact_metadata(config),
            subject=f"Artifact manifest {manifest_path}",
            error_code=error_code,
        )
        validate_artifact_metadata(
            metadata,
            expected_artifact_metadata(config),
            subject=f"Wheel {wheel}",
            error_code=error_code,
        )
        return BuiltArtifact(
            wheel=wheel,
            manifest_path=manifest_path,
            sha256=actual_sha256,
            metadata=metadata,
        )

    if require_manifest:
        raise CliError(
            (
                f"No target artifact manifest found in {manifest_path}. "
                f"Run build again for target {config.build.target_name}."
            ),
            error_code,
        )

    wheels = candidate_wheels(config)
    if not wheels:
        raise CliError(f"No built wheel found in {target_dist_dir(config)}", error_code)
    if require_unique and len(wheels) != 1:
        raise CliError(
            (
                f"Expected exactly one built wheel in {target_dist_dir(config)} for target "
                f"{config.build.target_name}, found {len(wheels)}."
            ),
            error_code,
        )
    wheel = wheels[0]
    metadata = load_wheel_artifact_metadata(wheel, error_code=error_code)
    validate_artifact_metadata(
        metadata,
        expected_artifact_metadata(config),
        subject=f"Wheel {wheel}",
        error_code=error_code,
    )
    return BuiltArtifact(
        wheel=wheel,
        manifest_path=None,
        sha256=file_sha256(wheel),
        metadata=metadata,
    )


def candidate_wheels(config: ResolvedConfig) -> list[Path]:
    dist_dir = target_dist_dir(config)
    distribution = config.build.distribution_name.replace("-", "_")
    return sorted(
        dist_dir.glob(f"{distribution}-*.whl"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )


def expected_artifact_metadata(config: ResolvedConfig) -> dict[str, Any]:
    return render_artifact_metadata(config)


def load_artifact_manifest(config: ResolvedConfig, *, error_code: int) -> dict[str, Any]:
    manifest_path = target_artifact_manifest_path(config)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CliError(f"No target artifact manifest found in {manifest_path}", error_code) from exc
    except json.JSONDecodeError as exc:
        raise CliError(f"Artifact manifest at {manifest_path} is invalid JSON: {exc}", error_code) from exc
    if not isinstance(payload, dict):
        raise CliError(f"Artifact manifest at {manifest_path} must be a JSON object.", error_code)
    return payload


def write_artifact_manifest(config: ResolvedConfig, wheel: Path, metadata: dict[str, Any]) -> Path:
    manifest_path = target_artifact_manifest_path(config)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "wheel": wheel.name,
                "sha256": file_sha256(wheel),
                "build": metadata,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest_path


def load_wheel_artifact_metadata(
    wheel: Path,
    *,
    error_code: int,
) -> dict[str, Any]:
    member_name = f"*.dist-info/{ARTIFACT_METADATA_FILENAME}"
    try:
        with zipfile.ZipFile(wheel) as archive:
            member_name = artifact_metadata_member(archive, error_code=error_code)
            raw_metadata = archive.read(member_name)
    except KeyError as exc:
        raise CliError(
            (
                f"Wheel {wheel} is missing target artifact metadata ({member_name}). "
                "Rebuild it with the current CLI."
            ),
            error_code,
        ) from exc
    except zipfile.BadZipFile as exc:
        raise CliError(f"Wheel {wheel} is not a valid zip archive: {exc}", error_code) from exc

    try:
        payload = json.loads(raw_metadata.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CliError(f"Wheel {wheel} has invalid target artifact metadata: {exc}", error_code) from exc
    if not isinstance(payload, dict):
        raise CliError(f"Wheel {wheel} target artifact metadata must be a JSON object.", error_code)
    return payload


def artifact_metadata_member(archive: zipfile.ZipFile, *, error_code: int) -> str:
    members = sorted(
        member
        for member in archive.namelist()
        if member.endswith(f".dist-info/{ARTIFACT_METADATA_FILENAME}")
    )
    if not members:
        raise KeyError(ARTIFACT_METADATA_FILENAME)
    if len(members) > 1:
        raise CliError(
            (
                f"Wheel contains multiple target artifact metadata files for {ARTIFACT_METADATA_FILENAME}: "
                + ", ".join(members)
            ),
            error_code,
        )
    return members[0]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_artifact_metadata(
    actual: Any,
    expected: dict[str, Any],
    *,
    subject: str,
    error_code: int,
) -> None:
    if not isinstance(actual, dict):
        raise CliError(f"{subject} metadata must be a JSON object.", error_code)

    mismatches: list[str] = []
    for key, expected_value in expected.items():
        if actual.get(key) != expected_value:
            mismatches.append(f"{key}={actual.get(key)!r} expected {expected_value!r}")

    if mismatches:
        raise CliError(
            (
                f"{subject} does not match selected target {expected['target_name']}: "
                + ", ".join(mismatches)
            ),
            error_code,
        )


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
