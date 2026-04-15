from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONDA_EXE = r"C:\Users\ZO\anaconda3\condabin\conda.bat"
DEFAULT_MAYA_PY = r"C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe"
DEFAULT_ENV_PATH = ".conda/maya-cython-build"
DEFAULT_CONFIG_NAME = ".maya-cython-compile.json"


@dataclass(slots=True)
class SmokeConfig:
    callable: str | None
    compiled_modules: list[str]
    resource_check: str | None


@dataclass(slots=True)
class BuildConfig:
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
    conda_exe: Path
    env_path: Path
    maya_py: Path
    config_path: Path


@dataclass(slots=True)
class ResolvedConfig:
    repo_root: Path
    build: BuildConfig
    local: LocalConfig


def default_config_path(repo_root: Path) -> Path:
    return repo_root / DEFAULT_CONFIG_NAME


def load_build_config(repo_root: Path) -> BuildConfig:
    payload = _read_json(repo_root / "build-config.json")
    smoke_payload = payload.get("smoke", {})
    return BuildConfig(
        distribution_name=payload["distribution_name"],
        package_name=payload["package_name"],
        package_dir=payload["package_dir"],
        module_name=payload.get("module_name", payload["package_name"]),
        maya_version=str(payload.get("maya_version", "2025")),
        version=payload["version"],
        compiled_modules=list(payload["compiled_modules"]),
        package_data=list(payload.get("package_data", [])),
        smoke=SmokeConfig(
            callable=smoke_payload.get("callable"),
            compiled_modules=list(
                smoke_payload.get("compiled_modules", payload.get("compiled_modules", []))
            ),
            resource_check=smoke_payload.get("resource_check"),
        ),
    )


def resolve_config(
    repo_root: Path,
    *,
    config_path: str | None = None,
    conda_exe: str | None = None,
    env_path: str | None = None,
    maya_py: str | None = None,
) -> ResolvedConfig:
    repo_root = repo_root.resolve()
    build = load_build_config(repo_root)
    config_file = Path(config_path).resolve() if config_path else default_config_path(repo_root)
    file_payload = _read_json(config_file) if config_file.exists() else {}

    resolved_conda = _resolve_path(
        repo_root,
        conda_exe
        or os.environ.get("MAYA_CYTHON_COMPILE_CONDA_EXE")
        or file_payload.get("conda_exe")
        or DEFAULT_CONDA_EXE,
    )
    resolved_env = _resolve_path(
        repo_root,
        env_path
        or os.environ.get("MAYA_CYTHON_COMPILE_ENV_PATH")
        or file_payload.get("env_path")
        or DEFAULT_ENV_PATH,
    )
    resolved_maya_py = _resolve_path(
        repo_root,
        maya_py
        or os.environ.get("MAYA_CYTHON_COMPILE_MAYA_PY")
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
    )


def as_dict(config: ResolvedConfig) -> dict[str, Any]:
    return {
        "repo_root": str(config.repo_root),
        "local_config_path": str(config.local.config_path),
        "conda_exe": str(config.local.conda_exe),
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
