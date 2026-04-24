from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import ResolvedConfig
from .errors import BUILD_ERROR, CliError
from .paths import target_artifact_manifest_path, target_dist_dir
from .target_builder import ARTIFACT_METADATA_FILENAME, render_artifact_metadata


@dataclass(frozen=True, slots=True)
class BuiltArtifact:
    wheel: Path
    manifest_path: Path | None
    sha256: str
    metadata: dict[str, Any]


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
