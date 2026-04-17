from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_CONDA_COMMAND = "conda"
DEFAULT_MAYA_PY = r"C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe"
DEFAULT_ENV_DIR = ".conda"
DEFAULT_PYTHON_VERSION = "3.11"
DEFAULT_CONFIG_NAME = ".maya-cython-compile.json"
DEFAULT_TARGET_NAME = "default"
PLATFORM_ALIASES = {
    "windows": "windows",
    "win": "windows",
    "win64": "windows",
    "linux": "linux",
    "linux64": "linux",
    "mac": "macos",
    "macos": "macos",
    "darwin": "macos",
    "osx": "macos",
}


@dataclass(slots=True)
class SmokeConfig:
    callable: str | None
    compiled_modules: list[str]
    resource_check: str | None


@dataclass(slots=True)
class BuildConfig:
    target_name: str
    platform: str
    python_version: str
    distribution_name: str
    package_name: str
    package_dir: str
    module_name: str
    maya_version: str
    version: str
    compiled_modules: list[str]
    package_data: list[str]
    smoke: SmokeConfig


@dataclass(slots=True)
class LocalConfig:
    conda_exe: str
    env_path: Path
    maya_py: Path
    config_path: Path


@dataclass(slots=True)
class ResolvedConfig:
    repo_root: Path
    build: BuildConfig
    local: LocalConfig
    available_targets: tuple[str, ...]


def default_config_path(repo_root: Path) -> Path:
    return repo_root / DEFAULT_CONFIG_NAME


def load_build_config(
    repo_root: Path,
    *,
    target_name: str | None = None,
    payload: dict[str, Any] | None = None,
) -> tuple[BuildConfig, tuple[str, ...]]:
    payload = payload or _read_json(repo_root / "build-config.json")
    resolved_target = _resolve_target_name(payload, target_name)
    build_payload = _resolve_build_payload(payload, resolved_target)
    smoke_payload = build_payload.get("smoke", {})
    return (
        BuildConfig(
            target_name=resolved_target,
            platform=_normalize_platform(build_payload.get("platform", "windows")),
            python_version=str(build_payload.get("python_version", DEFAULT_PYTHON_VERSION)),
            distribution_name=build_payload["distribution_name"],
            package_name=build_payload["package_name"],
            package_dir=build_payload["package_dir"],
            module_name=build_payload.get("module_name", build_payload["package_name"]),
            maya_version=str(build_payload.get("maya_version", "2025")),
            version=build_payload["version"],
            compiled_modules=list(build_payload["compiled_modules"]),
            package_data=list(build_payload.get("package_data", [])),
            smoke=SmokeConfig(
                callable=smoke_payload.get("callable"),
                compiled_modules=list(
                    smoke_payload.get("compiled_modules", build_payload.get("compiled_modules", []))
                ),
                resource_check=smoke_payload.get("resource_check"),
            ),
        ),
        _available_targets(payload),
    )


def resolve_config(
    repo_root: Path,
    *,
    config_path: str | None = None,
    target: str | None = None,
    conda_exe: str | None = None,
    env_path: str | None = None,
    maya_py: str | None = None,
) -> ResolvedConfig:
    repo_root = repo_root.resolve()
    config_file = Path(config_path).resolve() if config_path else default_config_path(repo_root)
    file_payload = _read_json(config_file) if config_file.exists() else {}
    build_payload = _read_json(repo_root / "build-config.json")
    build, available_targets = load_build_config(
        repo_root,
        target_name=target or os.environ.get("MAYA_CYTHON_COMPILE_TARGET") or file_payload.get("target"),
        payload=build_payload,
    )
    target_payload = _local_target_payload(file_payload, build.target_name)

    resolved_conda = _resolve_executable(
        repo_root,
        conda_exe
        or os.environ.get("MAYA_CYTHON_COMPILE_CONDA_EXE")
        or target_payload.get("conda_exe")
        or file_payload.get("conda_exe")
        or _default_conda_exe(),
    )
    resolved_env = _resolve_path(
        repo_root,
        env_path
        or os.environ.get("MAYA_CYTHON_COMPILE_ENV_PATH")
        or target_payload.get("env_path")
        or file_payload.get("env_path")
        or _default_env_path(build.target_name),
    )
    resolved_maya_py = _resolve_path(
        repo_root,
        maya_py
        or os.environ.get("MAYA_CYTHON_COMPILE_MAYA_PY")
        or target_payload.get("maya_py")
        or file_payload.get("maya_py")
        or DEFAULT_MAYA_PY,
    )

    return ResolvedConfig(
        repo_root=repo_root,
        build=build,
        local=LocalConfig(
            conda_exe=resolved_conda,
            env_path=resolved_env,
            maya_py=resolved_maya_py,
            config_path=config_file,
        ),
        available_targets=available_targets,
    )


def as_dict(config: ResolvedConfig) -> dict[str, Any]:
    return {
        "repo_root": str(config.repo_root),
        "local_config_path": str(config.local.config_path),
        "target": config.build.target_name,
        "available_targets": list(config.available_targets),
        "platform": config.build.platform,
        "python_version": config.build.python_version,
        "conda_exe": config.local.conda_exe,
        "env_path": str(config.local.env_path),
        "maya_py": str(config.local.maya_py),
        "distribution_name": config.build.distribution_name,
        "package_name": config.build.package_name,
        "package_dir": config.build.package_dir,
        "module_name": config.build.module_name,
        "maya_version": config.build.maya_version,
        "version": config.build.version,
        "compiled_modules": list(config.build.compiled_modules),
        "package_data": list(config.build.package_data),
        "smoke": {
            "callable": config.build.smoke.callable,
            "compiled_modules": list(config.build.smoke.compiled_modules),
            "resource_check": config.build.smoke.resource_check,
        },
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_path(repo_root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (repo_root / path).resolve()


def _resolve_executable(repo_root: Path, raw_value: str) -> str:
    path = Path(raw_value)
    if path.is_absolute():
        return str(path)
    if _is_explicit_relative_path(raw_value):
        return str((repo_root / path).resolve())

    discovered = shutil.which(raw_value)
    if discovered:
        return str(Path(discovered))

    candidate = (repo_root / path).resolve()
    if candidate.exists():
        return str(candidate)
    return raw_value


def _default_conda_exe() -> str:
    discovered = shutil.which(DEFAULT_CONDA_COMMAND)
    if discovered:
        return discovered
    if os.name == "nt":
        return str(Path.home() / "anaconda3" / "condabin" / "conda.bat")
    return DEFAULT_CONDA_COMMAND


def _default_env_path(target_name: str) -> str:
    return f"{DEFAULT_ENV_DIR}/{target_name}"


def _is_explicit_relative_path(raw_value: str) -> bool:
    return raw_value.startswith(".") or "/" in raw_value or "\\" in raw_value


def _available_targets(payload: dict[str, Any]) -> tuple[str, ...]:
    targets = payload.get("targets")
    if not isinstance(targets, dict) or not targets:
        return (DEFAULT_TARGET_NAME,)
    return tuple(targets.keys())


def _resolve_target_name(payload: dict[str, Any], requested_target: str | None) -> str:
    targets = payload.get("targets")
    if not isinstance(targets, dict) or not targets:
        if requested_target and requested_target != DEFAULT_TARGET_NAME:
            raise ValueError(
                f"build-config.json does not define named targets; remove --target {requested_target!r} "
                "or migrate to a targets map."
            )
        return DEFAULT_TARGET_NAME

    if requested_target:
        if requested_target not in targets:
            raise ValueError(f"Unknown target {requested_target!r}. Available targets: {', '.join(targets)}")
        return requested_target

    default_target = payload.get("default_target")
    if isinstance(default_target, str) and default_target:
        if default_target not in targets:
            raise ValueError(
                f"default_target {default_target!r} is not defined in build-config.json targets."
            )
        return default_target

    if len(targets) == 1:
        return next(iter(targets))

    raise ValueError("build-config.json defines multiple targets; select one with --target or set default_target.")


def _resolve_build_payload(payload: dict[str, Any], target_name: str) -> dict[str, Any]:
    targets = payload.get("targets")
    if not isinstance(targets, dict) or not targets:
        return payload

    target_payload = targets.get(target_name)
    if not isinstance(target_payload, dict):
        raise ValueError(f"Target {target_name!r} in build-config.json must be an object.")

    base_payload = {key: value for key, value in payload.items() if key not in {"default_target", "targets"}}
    return _merge_dicts(base_payload, target_payload)


def _local_target_payload(payload: dict[str, Any], target_name: str) -> dict[str, Any]:
    targets = payload.get("targets")
    if not isinstance(targets, dict):
        return {}
    target_payload = targets.get(target_name, {})
    if not isinstance(target_payload, dict):
        raise ValueError(f"Local config target {target_name!r} must be an object.")
    return target_payload


def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _normalize_platform(raw_platform: str) -> str:
    normalized = PLATFORM_ALIASES.get(str(raw_platform).lower())
    if normalized is None:
        raise ValueError(f"Unsupported target platform {raw_platform!r}.")
    return normalized
