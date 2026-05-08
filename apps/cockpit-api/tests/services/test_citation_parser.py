"""Tests for parse_citations — Story 6.8 / AC #10."""

from __future__ import annotations

from cockpit_api.services.citation_parser import parse_citations


def test_returns_empty_when_no_citations() -> None:
    assert parse_citations("hello world") == []


def test_returns_single_citation_in_order() -> None:
    text = "see led_01ABCDEFGHJKMNPQRSTVWXYZ12 for details"
    assert parse_citations(text) == ["led_01ABCDEFGHJKMNPQRSTVWXYZ12"]


def test_dedupes_repeated_citations() -> None:
    text = "led_01ABCDEFGHJKMNPQRSTVWXYZ12 then led_01ABCDEFGHJKMNPQRSTVWXYZ12 again"
    assert parse_citations(text) == ["led_01ABCDEFGHJKMNPQRSTVWXYZ12"]


def test_returns_multiple_in_first_seen_order() -> None:
    text = "first led_01ABCDEFGHJKMNPQRSTVWXYZ12 then led_23BCDEFGHJKMNPQRSTVWXYZ234 last"
    assert parse_citations(text) == [
        "led_01ABCDEFGHJKMNPQRSTVWXYZ12",
        "led_23BCDEFGHJKMNPQRSTVWXYZ234",
    ]


def test_does_not_match_truncated() -> None:
    assert parse_citations("led_01HXY3 short") == []


def test_does_not_match_capitalized_prefix() -> None:
    assert parse_citations("Led_01ABCDEFGHJKMNPQRSTVWXYZ12") == []
