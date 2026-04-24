from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .errors import DEPENDENCY_ERROR, INTERRUPTED_ERROR, CliError


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
    include_dir = _resolve_python_include_dir(
        payload.get("include_dir"),
        payload.get("platinclude_dir"),
        config_vars,
        python_prefix=payload.get("python_prefix"),
        python_base_prefix=payload.get("python_base_prefix"),
        maya_py=maya_py,
    )
    library_file = _resolve_python_library_file(
        config_vars,
        python_version=python_version,
        python_prefix=payload.get("python_prefix"),
        python_base_prefix=payload.get("python_base_prefix"),
        maya_py=maya_py,
        runtime_platform=runtime_platform,
    )
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


def is_interrupt_returncode(returncode: int) -> bool:
    return returncode in {
        130,
        -2,
        -1073741510,
        0xC000013A,
    }


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


def _resolve_python_include_dir(
    include_dir: str | None,
    platinclude_dir: str | None,
    config_vars: dict[str, Any],
    *,
    python_prefix: str | None,
    python_base_prefix: str | None,
    maya_py: Path,
) -> Path | None:
    resolved = _resolve_existing_path(
        include_dir,
        platinclude_dir,
        config_vars.get("INCLUDEPY"),
        config_vars.get("CONFINCLUDEPY"),
    )
    if resolved is not None:
        return resolved

    candidate_dirs: list[Path] = []
    for raw_prefix in (python_prefix, python_base_prefix):
        if not raw_prefix:
            continue
        prefix = Path(raw_prefix)
        candidate_dirs.extend(
            [
                prefix / "include",
                prefix / "Include",
                prefix.parent / "include",
                prefix.parent / "Include",
            ]
        )

    maya_runtime_root = maya_py.resolve().parent.parent if maya_py.exists() else maya_py.parent.parent
    candidate_dirs.extend(
        [
            maya_runtime_root / "include",
            maya_runtime_root / "Include",
            maya_runtime_root / "Python" / "include",
            maya_runtime_root / "Python" / "Include",
        ]
    )
    return _find_existing_directory(candidate_dirs)


def _resolve_python_library_file(
    config_vars: dict[str, Any],
    *,
    python_version: str | None,
    python_prefix: str | None,
    python_base_prefix: str | None,
    maya_py: Path,
    runtime_platform: str | None,
) -> Path | None:
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

    candidate_names.extend(_inferred_python_library_names(python_version, runtime_platform))
    candidate_dirs.extend(_inferred_python_library_dirs(python_prefix, python_base_prefix, maya_py))
    return _find_python_library_file(candidate_dirs, candidate_names)


def _inferred_python_library_names(
    python_version: str | None,
    runtime_platform: str | None,
) -> list[str]:
    if not python_version:
        return []
    version_parts = normalized_python_version(python_version)
    if len(version_parts) < 2:
        return []
    major, minor = version_parts[:2]
    if runtime_platform == "windows":
        return [f"python{major}{minor}.lib"]
    return [
        f"libpython{major}.{minor}.so",
        f"libpython{major}.{minor}.so.1.0",
        f"libpython{major}.{minor}.a",
        f"libpython{major}.{minor}.dylib",
    ]


def _inferred_python_library_dirs(
    python_prefix: str | None,
    python_base_prefix: str | None,
    maya_py: Path,
) -> list[Path]:
    candidate_dirs: list[Path] = []
    for raw_prefix in (python_prefix, python_base_prefix):
        if not raw_prefix:
            continue
        prefix = Path(raw_prefix)
        candidate_dirs.extend(
            [
                prefix / "lib",
                prefix / "libs",
                prefix.parent / "lib",
                prefix.parent / "libs",
            ]
        )

    maya_runtime_root = maya_py.resolve().parent.parent if maya_py.exists() else maya_py.parent.parent
    candidate_dirs.extend(
        [
            maya_runtime_root / "lib",
            maya_runtime_root / "libs",
            maya_runtime_root / "Python" / "lib",
            maya_runtime_root / "Python" / "libs",
        ]
    )
    return candidate_dirs


def _find_python_library_file(candidate_dirs: list[Path], candidate_names: list[str]) -> Path | None:
    unique_dirs = _unique_existing_directories(candidate_dirs)

    seen_names: set[str] = set()
    unique_names: list[str] = []
    for candidate_name in candidate_names:
        normalized = candidate_name.lower()
        if normalized in seen_names:
            continue
        seen_names.add(normalized)
        unique_names.append(candidate_name)

    for candidate_dir in unique_dirs:
        for candidate_name in unique_names:
            candidate_file = candidate_dir / candidate_name
            if candidate_file.exists():
                return candidate_file
    return None


def _find_existing_directory(candidate_dirs: list[Path]) -> Path | None:
    unique_dirs = _unique_existing_directories(candidate_dirs)
    return unique_dirs[0] if unique_dirs else None


def _unique_existing_directories(candidate_dirs: list[Path]) -> list[Path]:
    seen_dirs: set[Path] = set()
    unique_dirs: list[Path] = []
    for candidate_dir in candidate_dirs:
        if not candidate_dir.exists():
            continue
        resolved = candidate_dir.resolve()
        if resolved in seen_dirs:
            continue
        seen_dirs.add(resolved)
        unique_dirs.append(candidate_dir)
    return unique_dirs


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
