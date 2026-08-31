"""Digest-bound source lock helpers for generated icon collections."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable


MINIMUM_COUNT_RATIO_PERCENT = 75


def digest_files(root: Path, relative_paths: Iterable[Path]) -> str:
    """Hash selected source files with their paths so renames are observable."""

    digest = hashlib.sha256()
    for relative_path in sorted(relative_paths, key=lambda path: path.as_posix()):
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(f"Unsafe source path: {relative_path}")
        source_path = root / relative_path
        if not source_path.is_file():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        digest.update(relative_path.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(source_path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def write_lock(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def read_lock(path: Path, source: str, commit: str) -> dict:
    payload = _read_lock_payload(path)
    if payload.get("source") != source:
        raise ValueError(f"Source lock {path} is not for {source}")
    if payload.get("commit") != commit:
        raise ValueError(f"Source lock {path} does not match commit {commit}")
    digest = payload.get("contentSha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError(f"Source lock {path} has no valid content digest")
    return payload


def read_archive_lock(path: Path, source: str, archive_url: str, package_version: str) -> dict:
    """Read a digest-bound package archive lock without treating it as a Git source."""

    payload = _read_lock_payload(path)
    if payload.get("source") != source:
        raise ValueError(f"Source lock {path} is not for {source}")
    if payload.get("archiveUrl") != archive_url:
        raise ValueError(f"Source lock {path} does not match archive URL {archive_url}")
    if payload.get("packageVersion") != package_version:
        raise ValueError(
            f"Source lock {path} does not match package version {package_version}"
        )
    for field in ("archiveSha256", "contentSha256"):
        digest = payload.get(field)
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError(f"Source lock {path} has no valid {field}")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"Source lock {path} has no indexed archive entries")
    return payload


def validate_candidate_lock(
    candidate_path: Path,
    previous_path: Path,
    *,
    source: str,
    count_fields: tuple[str, ...],
    scope_fields: tuple[str, ...],
) -> dict:
    """Reject source-scope drift or a count below 75% of the prior lock."""

    candidate = _read_lock_payload(candidate_path)
    if candidate.get("source") != source:
        raise ValueError(f"Candidate source lock {candidate_path} is not for {source}")

    for field in count_fields:
        value = candidate.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(
                f"Candidate source lock {candidate_path} has invalid {field}"
            )

    if not previous_path.exists():
        raise ValueError(f"Previous source lock is required: {previous_path}")

    previous = _read_lock_payload(previous_path)
    if previous.get("source") != source:
        raise ValueError(f"Previous source lock {previous_path} is not for {source}")

    for field in scope_fields:
        if field not in candidate or field not in previous:
            raise ValueError(f"Source locks must define approved scope field {field}")
        if candidate.get(field) != previous.get(field):
            raise ValueError(
                f"Candidate source lock changes approved scope field {field}"
            )

    for field in count_fields:
        previous_value = previous.get(field)
        if previous_value is None:
            continue
        if (
            not isinstance(previous_value, int)
            or isinstance(previous_value, bool)
            or previous_value < 0
        ):
            raise ValueError(f"Previous source lock {previous_path} has invalid {field}")
        candidate_value = candidate[field]
        if candidate_value * 100 < previous_value * MINIMUM_COUNT_RATIO_PERCENT:
            raise ValueError(
                f"Candidate {field} collapsed from {previous_value} to "
                f"{candidate_value}, below {MINIMUM_COUNT_RATIO_PERCENT}% of prior"
            )

    return candidate


def _read_lock_payload(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read source lock {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid source lock {path}")
    return payload
