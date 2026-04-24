from __future__ import annotations

import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

from .errors import CliError


def ensure_path_within_directory(path: Path, root: Path, *, subject: str, error_code: int) -> Path:
    resolved_path = path.resolve(strict=False)
    resolved_root = root.resolve(strict=False)
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise CliError(f"{subject} must stay within {resolved_root}: {resolved_path}", error_code) from exc
    return resolved_path


def ensure_relative_path_under(path: Path, root: Path, *, subject: str) -> Path:
    resolved_path = path.resolve(strict=False)
    resolved_root = root.resolve(strict=False)
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"{subject} must stay within {resolved_root}: {resolved_path}") from exc
    return resolved_path


def safe_extract_all(archive: zipfile.ZipFile, destination: Path, *, error_code: int) -> None:
    for member in archive.infolist():
        safe_extract_member(archive, member, destination, error_code=error_code)


def safe_extract_member(
    archive: zipfile.ZipFile,
    member: zipfile.ZipInfo,
    destination: Path,
    *,
    error_code: int,
) -> None:
    _validate_archive_member_name(member.filename, error_code=error_code)
    ensure_path_within_directory(
        destination / member.filename,
        destination,
        subject=f"Archive member {member.filename!r}",
        error_code=error_code,
    )
    archive.extract(member, destination)


def _validate_archive_member_name(filename: str, *, error_code: int) -> None:
    posix_path = PurePosixPath(filename)
    windows_path = PureWindowsPath(filename)
    if (
        not filename
        or posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or ".." in posix_path.parts
        or ".." in windows_path.parts
    ):
        raise CliError(f"Archive member path is unsafe: {filename!r}", error_code)
