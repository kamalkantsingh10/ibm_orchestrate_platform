"""Mock screening adapter — Story 6.1 / AC #3.

Deterministic, offline. Lookup order per subject:

1. Exact key by ``(lowercased name, dob)`` against ``SCREENING_FIXTURES``.
2. Exact key by ``subject_id`` against ``SUBJECT_ID_OVERRIDES``.
3. Fuzzy fallback: ``rapidfuzz.fuzz.token_set_ratio`` against
   ``FUZZY_CORPUS``; emit one hit per name whose score ≥ 0.50.

All results carry ``ProvenancedField[float]`` with ``confidence ==
name_match_score`` (the mock's confidence in the hit IS the fuzz score).
``disposition`` defaults to ``"open"`` — auto-dismissal is the agent's job
(Story 6.2). The adapter never raises in the demo path.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime

from contracts.confidence import to_band
from contracts.provenance import Provenance, ProvenancedField
from contracts.screening import (
    ScreeningHit,
    ScreeningRequest,
    ScreeningSubject,
)
from rapidfuzz import fuzz

from agents.adapters.screening.fixtures import (
    FUZZY_CORPUS,
    SCREENING_FIXTURES,
    SUBJECT_ID_OVERRIDES,
    _RawHit,
)

_FUZZY_THRESHOLD = 0.50


class MockScreeningAdapter:
    """Deterministic in-memory screening lookup."""

    model_id: str = "screening_mock"

    async def screen(self, req: ScreeningRequest) -> list[ScreeningHit]:
        # Yield once so callers awaiting us don't run synchronously by accident.
        await asyncio.sleep(0)
        captured_at = datetime.now(UTC)
        out: list[ScreeningHit] = []
        for subject in req.subjects:
            out.extend(self._screen_subject(subject, captured_at))
        return out

    @staticmethod
    def _screen_subject(subject: ScreeningSubject, captured_at: datetime) -> list[ScreeningHit]:
        # 1. Exact (name, dob) lookup.
        key = (subject.full_name.lower().strip(), subject.date_of_birth)
        raw_hits = SCREENING_FIXTURES.get(key)
        if raw_hits is None and subject.date_of_birth is not None:
            # Fall back to (name, None) — the corpus uses None when DOB is
            # genuinely unknown (corporates, watchlist entries lacking DOB).
            raw_hits = SCREENING_FIXTURES.get((subject.full_name.lower().strip(), None))

        # 2. Subject-id override.
        if raw_hits is None:
            raw_hits = SUBJECT_ID_OVERRIDES.get(subject.subject_id)

        if raw_hits is not None:
            return [
                _build_hit(
                    raw=raw,
                    subject=subject,
                    score=raw.name_match_score,
                    captured_at=captured_at,
                )
                for raw in raw_hits
            ]

        # 3. Fuzzy fallback.
        return _fuzzy_hits(subject=subject, captured_at=captured_at)


def _fuzzy_hits(*, subject: ScreeningSubject, captured_at: datetime) -> list[ScreeningHit]:
    """Score the subject against ``FUZZY_CORPUS`` and emit hits ≥ 0.50."""
    out: list[ScreeningHit] = []
    for fixture_name in FUZZY_CORPUS:
        score = fuzz.token_set_ratio(subject.full_name, fixture_name) / 100.0
        if score < _FUZZY_THRESHOLD:
            continue
        # Reuse the matched name's pre-baked hit metadata so categories /
        # source lists stay consistent with the exact-match path. Fall back
        # to a "watchlist" placeholder if the corpus name lacks an entry.
        raw_hits = SCREENING_FIXTURES.get((fixture_name.lower().strip(), None))
        if raw_hits is None:
            # Walk all fixture rows for this name — DOB-keyed entries count too.
            for (k_name, _k_dob), candidates in SCREENING_FIXTURES.items():
                if k_name == fixture_name.lower().strip():
                    raw_hits = candidates
                    break
        if raw_hits is None:
            continue
        for raw in raw_hits:
            out.append(
                _build_hit(
                    raw=raw,
                    subject=subject,
                    score=score,
                    captured_at=captured_at,
                )
            )
    return out


def _build_hit(
    *,
    raw: _RawHit,
    subject: ScreeningSubject,
    score: float,
    captured_at: datetime,
) -> ScreeningHit:
    pf: ProvenancedField[float] = ProvenancedField(
        value=score,
        provenance=Provenance(
            source_agent="screening",
            source_system="screening_mock",
            confidence=score,
            confidence_band=to_band(score),
            evidence_ids=[],  # back-filled by Story 6.2 supervisor
            captured_at=captured_at,
        ),
    )
    return ScreeningHit(
        hit_id=_hit_id(subject.subject_id, raw.matched_name),
        subject_id=subject.subject_id,
        matched_name=raw.matched_name,
        name_match_score=pf,
        date_of_birth=raw.date_of_birth,
        identifiers=dict(raw.identifiers),
        categories=list(raw.categories),
        source_lists=list(raw.source_lists),
    )


def _hit_id(subject_id: str, matched_name: str) -> str:
    """Deterministic ``hit_mock_<sha1[:12]>`` per AC #3."""
    digest = hashlib.sha1(f"{subject_id}|{matched_name}".encode()).hexdigest()
    return f"hit_mock_{digest[:12]}"
