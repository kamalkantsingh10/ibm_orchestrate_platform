"""Unit tests for seed_dev helpers (Story 1.2)."""

from scripts.seed_dev import _normalise_dsn


def test_normalise_strips_asyncpg_driver() -> None:
    out = _normalise_dsn("postgresql+asyncpg://cockpit:cockpit@localhost:5432/cockpit")
    assert out == "postgresql://cockpit:cockpit@localhost:5432/cockpit"


def test_normalise_leaves_plain_dsn_alone() -> None:
    plain = "postgresql://cockpit:cockpit@localhost:5432/cockpit"
    assert _normalise_dsn(plain) == plain
