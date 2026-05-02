"""Document storage service — Story 3.8.

Owns the local filesystem for uploaded PDFs at
``./fixtures/uploads/<case_id>/<sanitized_filename>``. Pure helpers
(filename sanitization, magic-byte check, size cap, write/delete) so
the router stays thin.

Bank-buyer scope replaces this with an IBM COS / S3 / MinIO adapter via
``DocStore`` (deferred per the demo's local-filesystem stance).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from contracts.cases import is_valid_case_id

# Cap per file. The cockpit-api router streams multipart bodies; the cap
# is enforced as a byte-counter as the body is consumed.
MAX_BYTES = 10 * 1024 * 1024  # 10 MiB

# Magic bytes for PDF.
PDF_MAGIC = b"%PDF-"

# Safe filename pattern. No path separators, no traversal segments, .pdf only.
_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9._-]+\.pdf$")


class InvalidFilenameError(ValueError):
    """Filename failed the safe-name pattern."""


class FileTooLargeError(ValueError):
    """Body exceeded the per-file MAX_BYTES cap."""


class NotAPDFError(ValueError):
    """First few bytes did not match the PDF magic-byte signature."""


@dataclass(frozen=True)
class StoredDocument:
    """Metadata describing one document stored on disk."""

    filename: str
    size_bytes: int
    uploaded_at: datetime


def _uploads_root() -> Path:
    """Root directory for all uploads. Per-case subdir derived from this."""
    return Path("./fixtures/uploads")


def case_dir(case_id: str) -> Path:
    """Return the case-scoped upload directory.

    Caller is responsible for asserting the case exists (the router does
    this); this helper just builds the path. ``case_id`` is validated to
    avoid path traversal via a malicious value.
    """
    if not is_valid_case_id(case_id):
        # Defensive: the FastAPI path validator already enforces this, but
        # we re-check here so callers using the helper directly can't slip
        # in a `../` segment.
        raise InvalidFilenameError(f"invalid case_id: {case_id!r}")
    return _uploads_root() / case_id


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


def write_pdf(case_id: str, filename: str, body: bytes) -> StoredDocument:
    """Persist ``body`` as ``./fixtures/uploads/<case_id>/<filename>``.

    Caller must already have ``body`` fully buffered (we don't stream).
    Re-uploading the same filename overwrites.
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
