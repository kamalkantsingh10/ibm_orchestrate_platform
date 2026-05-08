"""Deterministic screening fixtures — Story 6.1 / AC #4.

Three case-pinned hit sets back the demo's J1 Screening narrative:

* **Vora Capital** — director Rohan Mehta (DIN 09876544 → ``ubo_p_09876544``)
  hits OFAC SDN at 0.73 with a DOB mismatch (registered 1961 vs subject's
  1978). The OFAC record's name is "Patel R." — i.e. a fuzzy namesake on the
  watchlist, not an exact match. The 0.73 score is hand-coded per AC #3
  (exact-key lookups bypass rapidfuzz). UX spec § J1 narrates "name 73%
  similar" verbatim.

* **Shree Venkat** — entity (Shree Venkat Trading) clean, no hits. Drives
  the demo's clean-approval path.

* **Ananya Iyer** — individual customer hits a synthetic PEP record at 0.88
  with DOB match. Drives the demo's secondary "happy-but-PEP" narrative.

Subject IDs match what the supervisor will hand the adapter from the live
UBO graph (``ubo_p_<din>`` for directors via
``apps/agents/src/agents/intake/ubo_graph.py``). Ananya is an
``individual`` case with no UBO graph — the supervisor passes her ``case_id``
as ``subject_id`` per Story 6.1 AC #4.

Story drafting note (deviation): the original AC text references a "Patel R."
director on the Vora UBO graph, but seeded MCA data
(``apps/agents/src/agents/tools/mca_mock.py``) lists Devansh Vora, Rohan
Mehta, and A K Filing Services. The hit is pinned to Rohan Mehta; the OFAC
record's matched_name is "Patel R." (the watchlist name, not the subject
name) — preserving the J1 narrative ("name 73% similar") without
back-editing Story 5 fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from contracts.cases import ANANYA_IYER_ID
from contracts.screening import ScreeningCategory


@dataclass(frozen=True)
class _RawHit:
    """Pre-baked hit record — turned into a ``ScreeningHit`` by the adapter."""

    matched_name: str
    name_match_score: float
    categories: tuple[ScreeningCategory, ...]
    source_lists: tuple[str, ...]
    date_of_birth: date | None = None
    identifiers: dict[str, str] = field(default_factory=dict)


# ───────────────────────── exact-key fixture corpus ─────────────────────────
#
# Keyed by (lowercased full_name, optional DOB). Subject IDs are matched
# only via ``SUBJECT_ID_OVERRIDES`` below — by-name lookup is the primary
# path so the fuzzy fallback shares the same matched_name corpus.

# Vora Capital — Rohan Mehta director hits OFAC SDN
_ROHAN_MEHTA_OFAC = _RawHit(
    matched_name="Patel R.",
    name_match_score=0.73,
    categories=("sanctions",),
    source_lists=("OFAC SDN",),
    date_of_birth=date(1961, 5, 12),
)

# Ananya Iyer — synthetic PEP hit
_ANANYA_PEP = _RawHit(
    matched_name="Ananya Iyer",
    name_match_score=0.88,
    categories=("pep",),
    source_lists=("OpenSanctions Politicians",),
    date_of_birth=date(1985, 11, 4),
)


# Primary lookup table: (lowercased name, optional DOB) → list[_RawHit]
SCREENING_FIXTURES: dict[tuple[str, date | None], list[_RawHit]] = {
    ("rohan mehta", None): [_ROHAN_MEHTA_OFAC],
    ("ananya iyer", date(1985, 11, 4)): [_ANANYA_PEP],
}

# Secondary lookup: subject_id → list[_RawHit]. Used for individuals whose
# subject_id is the case_id (Ananya — see AC #4) and any subject the
# supervisor passes whose ID is more reliable than its name.
SUBJECT_ID_OVERRIDES: dict[str, list[_RawHit]] = {
    "ubo_p_09876544": [_ROHAN_MEHTA_OFAC],  # Rohan Mehta, Vora director
    ANANYA_IYER_ID: [_ANANYA_PEP],
}

# Name corpus the fuzzy fallback scans. Keep small + deterministic.
FUZZY_CORPUS: tuple[str, ...] = (
    "Rohan Mehta",
    "Ananya Iyer",
)
