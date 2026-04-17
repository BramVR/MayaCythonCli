from __future__ import annotations

import os
import shutil
from pathlib import Path

from .errors import DEPENDENCY_ERROR, CliError

DEFAULT_CONDA_COMMAND = "conda"


def default_conda_exe() -> str:
    discovered = shutil.which(DEFAULT_CONDA_COMMAND)
    if discovered:
        return discovered
    if os.name == "nt":
        return str(Path.home() / "anaconda3" / "condabin" / "conda.bat")
    return DEFAULT_CONDA_COMMAND


def resolve_conda_executable(repo_root: Path, raw_value: str) -> str:
    path = Path(raw_value)
    if path.is_absolute():
        return str(path)
    if _looks_like_path(raw_value):
        return str((repo_root / path).resolve())

    discovered = shutil.which(raw_value)
    if discovered:
        return str(Path(discovered))

    candidate = (repo_root / path).resolve()
    if candidate.exists():
        return str(candidate)
    return raw_value


def conda_executable_exists(executable: str) -> bool:
    if _looks_like_path(executable):
        return Path(executable).exists()
    return shutil.which(executable) is not None


def conda_command(conda_exe: str, *args: str) -> list[str]:
    resolved = _resolve_executable_for_spawn(conda_exe)
    if Path(resolved).suffix.lower() in {".bat", ".cmd"}:
        if os.name != "nt":
            raise CliError(
                f"Batch Conda entrypoints are only supported on Windows: {resolved}",
                DEPENDENCY_ERROR,
            )
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", resolved, *args]
    return [resolved, *args]


def _resolve_executable_for_spawn(executable: str) -> str:
    if _looks_like_path(executable):
        return executable
    discovered = shutil.which(executable)
    return discovered or executable


def _looks_like_path(raw_value: str) -> bool:
    return Path(raw_value).is_absolute() or raw_value.startswith(".") or "/" in raw_value or "\\" in raw_value
