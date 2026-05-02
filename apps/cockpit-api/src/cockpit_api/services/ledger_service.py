"""Append-only JSONL ledger — Story 3.1.

The single mutation API is ``LedgerWriter.append``; no other mutating verb
exists in this module — see Story 3-1 § AC3. Bank-buyer-scope replacement:
Postgres ``ledger.ledger_entries`` table + INSERT-only role + UPDATE/DELETE
triggers + Ed25519 hash chain. The demo collapses all of that into JSONL +
module-level discipline.

Topology assumptions:
* Single-process single-uvicorn-worker (architecture A3). The ``asyncio.Lock``
  serializes appends *within* one event loop. Multi-worker deployments would
  need ``fcntl.flock`` or similar — out of scope for the demo.
* The file lives at ``Settings.ledger_path`` (default ``./data/ledger.jsonl``).
  Created lazily on first ``append`` so the empty-file shouldn't appear
  during ``alembic`` invocations or lint passes that import this module.

Read robustness:
* Tail-drop a partial last line (no trailing ``\\n``) with a WARN log; this
  is the recovery path for a power-cycle mid-write.
* Mid-file malformed JSON raises ``LedgerCorruptionError`` because something
  other than the writer touched the file — better to surface than swallow.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import aiofiles
from contracts.cases import CaseId
from contracts.ledger import LedgerEntry
from pydantic import ValidationError
from ulid import ULID

from cockpit_api.config import get_settings

logger = logging.getLogger(__name__)


class LedgerCorruptionError(RuntimeError):
    """Raised when a mid-file JSONL line fails to validate as ``LedgerEntry``.

    The append-only writer never produces malformed mid-file lines. If we
    see one, an out-of-band actor (e.g., a hand-edit) corrupted the file.
    """


# ───────────────────────────── writer ──────────────────────────────────────


class LedgerWriter:
    """Append-only JSONL writer. The public surface is exactly ``append``."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = asyncio.Lock()

    async def append(self, entry: LedgerEntry) -> LedgerEntry:
        """Append ``entry`` to the ledger.

        ``id`` is regenerated server-side via ULID and ``recorded_at`` is
        replaced with ``datetime.now(UTC)`` — caller-supplied values are
        ignored. Returns the canonical entry that landed on disk.

        If the writer fails to durably persist the entry, the exception
        propagates — callers must treat the entry as not-recorded.
        """
        async with self._lock:
            new_id = f"led_{ULID()!s}"
            now = datetime.now(UTC)
            canonical = entry.model_copy(update={"id": new_id, "recorded_at": now})
            self._path.parent.mkdir(parents=True, exist_ok=True)
            line = canonical.model_dump_json().encode("utf-8") + b"\n"
            # aiofiles' open in append-binary mode yields the loop on IO.
            async with aiofiles.open(self._path, mode="ab") as f:
                await f.write(line)
                await f.flush()
                # fsync against demo-laptop crash mid-write.
                fileno = f.fileno()
                os.fsync(fileno)
            return canonical


# ───────────────────────────── reader ──────────────────────────────────────


class LedgerReader:
    """Read-only view over the JSONL ledger."""

    def __init__(self, path: Path) -> None:
        self._path = path

    async def read_all(self) -> list[LedgerEntry]:
        """Return entries in append order. Empty list if file is missing."""
        if not self._path.exists():
            return []
        return await self._read_lines()

    async def read_for_case(self, case_id: CaseId) -> list[LedgerEntry]:
        """Return entries matching ``case_id`` in append order."""
        return [e for e in await self.read_all() if e.case_id == case_id]

    async def read_latest_by_actor(self, case_id: CaseId, actor_id: str) -> LedgerEntry | None:
        """Return the chronologically last entry for ``(case_id, actor_id)``."""
        match: LedgerEntry | None = None
        for entry in await self.read_all():
            if entry.case_id == case_id and entry.actor_id == actor_id:
                match = entry
        return match

    async def count(self) -> int:
        """Return total entry count."""
        if not self._path.exists():
            return 0
        return len(await self._read_lines())

    # ─── internal ───

    async def _read_lines(self) -> list[LedgerEntry]:
        """Stream the file line-by-line, validating each entry.

        Tail-drop a partial last line; raise on mid-file corruption.
        """
        entries: list[LedgerEntry] = []
        async with aiofiles.open(self._path, mode="rb") as f:
            content = await f.read()

        if not content:
            return entries

        # Split on b"\n" preserving the trailing-newline information.
        # If the file ends without "\n", the final element is the partial line.
        raw_lines = content.split(b"\n")
        # When the file ends in "\n", split produces a final empty element
        # which we discard. Otherwise the final element is a torn partial.
        ends_with_newline = content.endswith(b"\n")
        if ends_with_newline:
            raw_lines = raw_lines[:-1]
            torn_tail: bytes | None = None
        else:
            torn_tail = raw_lines[-1]
            raw_lines = raw_lines[:-1]

        for idx, raw in enumerate(raw_lines, start=1):
            if not raw:
                # Empty mid-file line — treat as corruption (the writer never produces these).
                raise LedgerCorruptionError(f"corrupt entry at line {idx}: empty line in ledger {self._path}")
            try:
                entries.append(LedgerEntry.model_validate_json(raw))
            except ValidationError as exc:
                raise LedgerCorruptionError(f"corrupt entry at line {idx}: {exc}") from exc

        if torn_tail is not None:
            tail_line_no = len(raw_lines) + 1
            logger.warning("ledger.tail_dropped path=%s line=%d", self._path, tail_line_no)

        return entries


# ───────────────────────────── singletons ──────────────────────────────────


@lru_cache(maxsize=1)
def get_ledger_writer() -> LedgerWriter:
    """Process-wide writer bound to ``Settings.ledger_path``."""
    return LedgerWriter(get_settings().ledger_path)


@lru_cache(maxsize=1)
def get_ledger_reader() -> LedgerReader:
    """Process-wide reader bound to ``Settings.ledger_path``."""
    return LedgerReader(get_settings().ledger_path)
