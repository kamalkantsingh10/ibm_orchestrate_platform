"""Tests for the JSONL ledger writer + reader — Story 3.1 / AC #8."""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path

import pytest
from contracts.cases import ANANYA_IYER_ID, SHREE_VENKAT_ID, VORA_CAPITAL_ID
from contracts.ledger import ActorType, LedgerEntry
from ulid import ULID

from cockpit_api.services.ledger_service import (
    LedgerCorruptionError,
    LedgerReader,
    LedgerWriter,
)


def _placeholder_id() -> str:
    """Pattern-valid ID. The writer regenerates it on append."""
    return f"led_{ULID()!s}"


def _stub_entry(
    *,
    case_id: str | None = SHREE_VENKAT_ID,
    actor_type: ActorType = ActorType.AGENT,
    actor_id: str = "document_intelligence",
    action: str = "agent.invoked",
    payload: dict[str, object] | None = None,
) -> LedgerEntry:
    """Build a valid stub. ``id`` and ``recorded_at`` will be overwritten by ``append``."""
    return LedgerEntry(
        id=_placeholder_id(),
        actor_type=actor_type,
        actor_id=actor_id,
        case_id=case_id,
        action=action,
        payload=payload or {"k": "v"},
        recorded_at=datetime.now(UTC),
    )


@pytest.fixture
def writer_and_reader(tmp_path: Path) -> tuple[LedgerWriter, LedgerReader]:
    path = tmp_path / "ledger.jsonl"
    return LedgerWriter(path), LedgerReader(path)


# ───────────── append basics ─────────────


async def test_append_returns_canonical_entry_with_server_id_and_timestamp(
    writer_and_reader: tuple[LedgerWriter, LedgerReader],
) -> None:
    writer, _ = writer_and_reader
    before = datetime.now(UTC)
    canonical = await writer.append(_stub_entry())
    after = datetime.now(UTC)

    assert re.match(r"^led_[0-9A-HJKMNP-TV-Z]{26}$", canonical.id)
    assert before <= canonical.recorded_at <= after


async def test_append_overwrites_caller_supplied_id_and_recorded_at(
    writer_and_reader: tuple[LedgerWriter, LedgerReader],
) -> None:
    writer, reader = writer_and_reader
    placeholder = _placeholder_id()
    arbitrary = LedgerEntry(
        id=placeholder,
        actor_type=ActorType.SYSTEM,
        actor_id="seed_dev",
        case_id=None,
        action="ledger.initialized",
        payload={"cases_seeded": 3},
        recorded_at=datetime(2000, 1, 1, tzinfo=UTC),
    )
    canonical = await writer.append(arbitrary)
    assert canonical.id != placeholder
    assert canonical.recorded_at.year >= 2026


# ───────────── 50 sequential appends ─────────────


async def test_50_sequential_appends_preserve_order_and_independence(
    writer_and_reader: tuple[LedgerWriter, LedgerReader],
) -> None:
    writer, reader = writer_and_reader
    expected_actor_ids = []
    for i in range(50):
        canonical = await writer.append(_stub_entry(actor_id=f"agent_{i:02d}", payload={"i": i}))
        expected_actor_ids.append((canonical.id, f"agent_{i:02d}"))

    entries = await reader.read_all()
    assert len(entries) == 50
    actual = [(e.id, e.actor_id) for e in entries]
    assert actual == expected_actor_ids
    assert await reader.count() == 50


# ───────────── filter helpers ─────────────


async def test_read_for_case_filters_by_case_id(
    writer_and_reader: tuple[LedgerWriter, LedgerReader],
) -> None:
    writer, reader = writer_and_reader
    await writer.append(_stub_entry(case_id=SHREE_VENKAT_ID, action="a.1"))
    await writer.append(_stub_entry(case_id=VORA_CAPITAL_ID, action="b.1"))
    await writer.append(_stub_entry(case_id=SHREE_VENKAT_ID, action="a.2"))
    await writer.append(
        _stub_entry(
            case_id=None,
            actor_type=ActorType.SYSTEM,
            actor_id="seed_dev",
            action="ledger.initialized",
        )
    )

    shree = await reader.read_for_case(SHREE_VENKAT_ID)
    vora = await reader.read_for_case(VORA_CAPITAL_ID)
    ananya = await reader.read_for_case(ANANYA_IYER_ID)

    assert [e.action for e in shree] == ["a.1", "a.2"]
    assert [e.action for e in vora] == ["b.1"]
    assert ananya == []


async def test_read_latest_by_actor_returns_chronological_last(
    writer_and_reader: tuple[LedgerWriter, LedgerReader],
) -> None:
    writer, reader = writer_and_reader
    await writer.append(_stub_entry(actor_id="document_intelligence", action="a.1"))
    await writer.append(_stub_entry(actor_id="entity_verification", action="b.1"))
    await writer.append(_stub_entry(actor_id="document_intelligence", action="a.2"))

    latest = await reader.read_latest_by_actor(SHREE_VENKAT_ID, "document_intelligence")
    assert latest is not None
    assert latest.action == "a.2"

    miss = await reader.read_latest_by_actor(VORA_CAPITAL_ID, "document_intelligence")
    assert miss is None


# ───────────── append-only invariant ─────────────


def test_writer_public_surface_is_exactly_append() -> None:
    public = {name for name in dir(LedgerWriter) if not name.startswith("_")}
    assert public == {"append"}, public


# ───────────── tail-drop behavior ─────────────


async def test_tail_drop_logs_warn_and_returns_valid_entries(
    writer_and_reader: tuple[LedgerWriter, LedgerReader],
    caplog: pytest.LogCaptureFixture,
) -> None:
    writer, reader = writer_and_reader
    await writer.append(_stub_entry(action="a.1"))
    await writer.append(_stub_entry(action="a.2"))
    # Manually corrupt the tail: append a partial line with no terminator.
    with open(reader._path, "ab") as f:
        f.write(b'{"id":"led_01HZZZZZZZZZZZZZZZZZZZZZZZ","actor_typ')

    with caplog.at_level(logging.WARNING):
        entries = await reader.read_all()

    assert len(entries) == 2
    assert any("tail_dropped" in record.message for record in caplog.records)


# ───────────── mid-file corruption ─────────────


async def test_mid_file_corruption_raises(
    writer_and_reader: tuple[LedgerWriter, LedgerReader],
) -> None:
    writer, reader = writer_and_reader
    await writer.append(_stub_entry(action="a.1"))
    # Corrupt the file by inserting a garbage line in the middle.
    with open(reader._path, "rb") as f:
        original = f.read()
    with open(reader._path, "wb") as f:
        f.write(original)
        f.write(b"GARBAGE_LINE\n")
        f.write(original)

    with pytest.raises(LedgerCorruptionError) as excinfo:
        await reader.read_all()
    assert "line 2" in str(excinfo.value)


# ───────────── concurrent appends ─────────────


async def test_concurrent_appends_serialize_cleanly(
    writer_and_reader: tuple[LedgerWriter, LedgerReader],
) -> None:
    writer, reader = writer_and_reader
    # 20 concurrent appends, each with a 1KB random blob — interleaving would
    # corrupt at least one line, which the reader would surface.
    await asyncio.gather(*[writer.append(_stub_entry(payload={"big": secrets.token_hex(512)})) for _ in range(20)])
    entries = await reader.read_all()
    assert len(entries) == 20
    # Each entry's payload "big" is a 1024-char hex string.
    for entry in entries:
        assert isinstance(entry.payload, dict)
        assert len(entry.payload["big"]) == 1024


# ───────────── lazy file creation ─────────────


async def test_file_created_lazily_on_first_append(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    reader = LedgerReader(path)

    assert not path.exists()
    assert await reader.read_all() == []  # safe before any append
    assert await reader.count() == 0

    await writer.append(_stub_entry())
    assert path.exists()

    entries = await reader.read_all()
    assert len(entries) == 1


# ───────────── Story 6.5 — read_by_id ─────────────


async def test_read_by_id_returns_entry_with_matching_id(
    writer_and_reader: tuple[LedgerWriter, LedgerReader],
) -> None:
    writer, reader = writer_and_reader
    appended = await writer.append(_stub_entry(actor_id="screening"))
    found = await reader.read_by_id(appended.id)
    assert found is not None
    assert found.id == appended.id
    assert found.actor_id == "screening"


async def test_read_by_id_returns_none_for_missing_id(
    writer_and_reader: tuple[LedgerWriter, LedgerReader],
) -> None:
    writer, reader = writer_and_reader
    await writer.append(_stub_entry())
    fake_id = f"led_{ULID()!s}"
    assert await reader.read_by_id(fake_id) is None


async def test_read_by_id_consistent_across_multiple_appends(
    writer_and_reader: tuple[LedgerWriter, LedgerReader],
) -> None:
    writer, reader = writer_and_reader
    ids: list[str] = []
    for i in range(5):
        appended = await writer.append(_stub_entry(actor_id=f"agent_{i}"))
        ids.append(appended.id)
    for i, eid in enumerate(ids):
        found = await reader.read_by_id(eid)
        assert found is not None
        assert found.actor_id == f"agent_{i}"
