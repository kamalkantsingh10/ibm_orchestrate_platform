"""Document storage service — Stories 3.8 and 8.5.

Story 3.8 owned PDF intake under ``./fixtures/uploads/<case_id>/``.
Story 8.5 adds an *evidence* kind that accepts a wider MIME whitelist
(PDF, PNG, JPG, plain text, .eml) and persists under
``./fixtures/uploads/<case_id>/evidence/``. The two kinds share the
case dir but live in disjoint subdirs so audit can list each
independently.

Pure helpers (filename sanitization, magic-byte check, size cap,
write/delete) so the router stays thin.

Bank-buyer scope replaces this with an IBM COS / S3 / MinIO adapter via
``DocStore`` (deferred per the demo's local-filesystem stance).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from contracts.cases import is_valid_case_id

from cockpit_api.config import get_settings

# Cap per file. The cockpit-api router streams multipart bodies; the cap
# is enforced as a byte-counter as the body is consumed.
MAX_BYTES = 10 * 1024 * 1024  # 10 MiB

# Magic bytes for PDF.
PDF_MAGIC = b"%PDF-"

# Safe filename pattern. No path separators, no traversal segments, .pdf only.
_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9._-]+\.pdf$")

# Story 8.5 — evidence file extensions. The router rejects anything
# outside this whitelist with HTTP 415.
DocumentKind = Literal["intake", "evidence"]
_EVIDENCE_EXT = re.compile(r"^[A-Za-z0-9._-]+\.(pdf|png|jpg|jpeg|txt|eml)$", re.IGNORECASE)


class InvalidFilenameError(ValueError):
    """Filename failed the safe-name pattern."""


class FileTooLargeError(ValueError):
    """Body exceeded the per-file MAX_BYTES cap."""


class NotAPDFError(ValueError):
    """First few bytes did not match the PDF magic-byte signature."""


@dataclass(frozen=True)
class StoredDocument:
    """Metadata describing one document stored on disk.

    Story 8.6 — ``sha256`` is the integrity anchor for evidence
    uploads (Story 8.6 / AC #1, #5). Also computed for intake uploads;
    cockpit-ui surfaces it in tooltips and the optional client-side
    re-hash check.
    """

    filename: str
    size_bytes: int
    uploaded_at: datetime
    sha256: str = ""


def _uploads_root() -> Path:
    """Root directory for all uploads. Per-case subdir derived from this.

    Sourced from ``Settings.uploads_root`` so the Makefile can pin a
    repo-root-anchored path regardless of the API's cwd.
    """
    return get_settings().uploads_root


def case_dir(case_id: str, kind: DocumentKind = "intake") -> Path:
    """Return the case-scoped upload directory.

    Caller is responsible for asserting the case exists (the router does
    this); this helper just builds the path. ``case_id`` is validated to
    avoid path traversal via a malicious value. Story 8.5 — when
    ``kind == 'evidence'``, the path nests one level deeper under
    ``evidence/`` so audit can list intake vs evidence independently.
    """
    if not is_valid_case_id(case_id):
        # Defensive: the FastAPI path validator already enforces this, but
        # we re-check here so callers using the helper directly can't slip
        # in a `../` segment.
        raise InvalidFilenameError(f"invalid case_id: {case_id!r}")
    base = _uploads_root() / case_id
    if kind == "evidence":
        return base / "evidence"
    return base


def sanitize_filename(name: str) -> str:
    """Validate ``name`` against the safe pattern; return as-is if valid.

    Raises ``InvalidFilenameError`` on path separators, traversal segments,
    non-PDF extensions, or non-alphanumeric chars beyond `._-`.
    """
    # Strip just to be safe (multipart sometimes carries trailing whitespace).
    candidate = name.strip()
    if not candidate or len(candidate) > 100:
        raise InvalidFilenameError(f"filename length out of bounds: {name!r}")
    if not _SAFE_FILENAME.match(candidate):
        raise InvalidFilenameError(f"filename {name!r} must match [A-Za-z0-9._-]+\\.pdf")
    if ".." in candidate or "/" in candidate or "\\" in candidate:
        raise InvalidFilenameError(f"filename {name!r} contains path separators")
    return candidate


def _hash_bytes(body: bytes) -> str:
    """Story 8.6 — return the SHA-256 hex digest of ``body``. Demo
    implementation buffers the body in memory (the router does the
    same); a streaming variant lives behind the same return type when
    needed."""
    return hashlib.sha256(body).hexdigest()


def write_pdf(case_id: str, filename: str, body: bytes) -> StoredDocument:
    """Persist ``body`` as ``./fixtures/uploads/<case_id>/<filename>``.

    Caller must already have ``body`` fully buffered (we don't stream).
    Re-uploading the same filename overwrites.

    Story 8.6 / AC #1, #5 — also computes the SHA-256 of ``body``.
    """
    safe_name = sanitize_filename(filename)
    if len(body) > MAX_BYTES:
        raise FileTooLargeError(f"body of {len(body)} bytes exceeds cap of {MAX_BYTES}")
    if not body.startswith(PDF_MAGIC):
        raise NotAPDFError(f"file {filename!r} is not a PDF (missing magic bytes)")

    target_dir = case_dir(case_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / safe_name
    path.write_bytes(body)
    stat = path.stat()
    return StoredDocument(
        filename=safe_name,
        size_bytes=stat.st_size,
        uploaded_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        sha256=_hash_bytes(body),
    )


def list_documents(case_id: str) -> list[StoredDocument]:
    """Return all stored docs for ``case_id``. Empty list if dir is missing."""
    target_dir = case_dir(case_id)
    if not target_dir.exists():
        return []
    out: list[StoredDocument] = []
    for path in sorted(target_dir.iterdir()):
        if not path.is_file() or not path.name.endswith(".pdf"):
            continue
        stat = path.stat()
        out.append(
            StoredDocument(
                filename=path.name,
                size_bytes=stat.st_size,
                uploaded_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                sha256=_hash_bytes(path.read_bytes()),
            )
        )
    return out


def delete_document(case_id: str, filename: str) -> bool:
    """Delete the file. Returns True if a file was removed; False if missing."""
    safe_name = sanitize_filename(filename)
    path = case_dir(case_id) / safe_name
    if not path.exists():
        return False
    path.unlink()
    return True


def get_document_path(case_id: str, filename: str) -> Path | None:
    """Return the on-disk path if the document exists, else ``None``.

    Validates ``case_id`` and ``filename`` against the safe-name pattern so
    the router can serve untrusted-input filenames without path traversal.
    """
    safe_name = sanitize_filename(filename)
    path = case_dir(case_id) / safe_name
    return path if path.exists() and path.is_file() else None


# ─── Story 8.5 — evidence ingest ─────────────────────────────────────────────


def sanitize_evidence_filename(name: str) -> str:
    """Validate ``name`` against the broader evidence pattern. Accepts
    `.pdf`, `.png`, `.jpg`, `.jpeg`, `.txt`, `.eml`. Same path-traversal
    guards as ``sanitize_filename``."""
    candidate = name.strip()
    if not candidate or len(candidate) > 100:
        raise InvalidFilenameError(f"filename length out of bounds: {name!r}")
    if not _EVIDENCE_EXT.match(candidate):
        raise InvalidFilenameError(f"filename {name!r} must match [A-Za-z0-9._-]+\\.(pdf|png|jpg|jpeg|txt|eml)")
    if ".." in candidate or "/" in candidate or "\\" in candidate:
        raise InvalidFilenameError(f"filename {name!r} contains path separators")
    return candidate


def write_evidence(case_id: str, filename: str, body: bytes) -> StoredDocument:
    """Persist ``body`` as ``./fixtures/uploads/<case_id>/evidence/<filename>``.

    Story 8.5 — accepts the broader evidence MIME whitelist (PDF, PNG,
    JPG, plain text, .eml) without magic-byte validation (the demo
    treats the file extension as the source of truth; a real platform
    should sniff content). Re-uploading the same filename overwrites.

    Story 8.6 / AC #1 — also computes the SHA-256 of ``body``; the
    router uses the digest as the integrity anchor on the
    ``case.evidence_attached`` ledger entry.
    """
    safe_name = sanitize_evidence_filename(filename)
    if len(body) > MAX_BYTES:
        raise FileTooLargeError(f"body of {len(body)} bytes exceeds cap of {MAX_BYTES}")
    target_dir = case_dir(case_id, kind="evidence")
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / safe_name
    path.write_bytes(body)
    stat = path.stat()
    return StoredDocument(
        filename=safe_name,
        size_bytes=stat.st_size,
        uploaded_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        sha256=_hash_bytes(body),
    )


def list_evidence(case_id: str) -> list[StoredDocument]:
    """Return all stored evidence files for ``case_id``. Empty list if dir is missing.

    Story 8.6 / AC #1 — sha256 is computed from the on-disk bytes so
    list responses match the upload-response anchor.
    """
    target_dir = case_dir(case_id, kind="evidence")
    if not target_dir.exists():
        return []
    out: list[StoredDocument] = []
    for path in sorted(target_dir.iterdir()):
        if not path.is_file():
            continue
        stat = path.stat()
        out.append(
            StoredDocument(
                filename=path.name,
                size_bytes=stat.st_size,
                uploaded_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                sha256=_hash_bytes(path.read_bytes()),
            )
        )
    # Newest first for the EvidenceShelf list (Story 8.5 / AC #1).
    return sorted(out, key=lambda d: d.uploaded_at, reverse=True)


def delete_evidence(case_id: str, filename: str) -> bool:
    """Delete the evidence file. Returns True if a file was removed; False if missing."""
    safe_name = sanitize_evidence_filename(filename)
    path = case_dir(case_id, kind="evidence") / safe_name
    if not path.exists():
        return False
    path.unlink()
    return True


def get_evidence_path(case_id: str, filename: str) -> Path | None:
    """Return the on-disk path if the evidence file exists, else ``None``."""
    safe_name = sanitize_evidence_filename(filename)
    path = case_dir(case_id, kind="evidence") / safe_name
    return path if path.exists() and path.is_file() else None
