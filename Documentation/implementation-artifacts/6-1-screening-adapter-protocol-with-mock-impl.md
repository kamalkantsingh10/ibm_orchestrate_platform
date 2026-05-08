# Story 6.1: Screening adapter Protocol with mock impl

Status: review

## Story

As the platform,
I want a `ScreeningAdapter` Protocol with Pydantic-typed request/hit contracts and a deterministic mock implementation keyed by name+DOB,
So that Story 6-2's Screening agent can run end-to-end in the local demo without any external vendor dependency, and Path B reviewers see the same Pluggable Adapter Pattern (P1) the Document Intelligence stack uses (FR18, NFR-RI1 ADK pattern coverage, demo-resolved decision §"Screening vendor selection → mock-only").

## Scope note (2026-04-29 demo re-scope)

This story is the **mock-only half** of the bank-buyer Story 6.1 + 6.2 pair. The bank-buyer scope shipped a mock impl AND a ComplyAdvantage impl side-by-side with a contract conformance suite (NFR-RI6). The demo re-scope drops the ComplyAdvantage impl, drops the conformance suite as a separate harness, and drops the procurement runbook (bank-buyer Story 6.10).

| Bank-buyer scope (original 6.1 + 6.2) | Demo replacement in this story |
|---|---|
| `ScreeningAdapter` Protocol + mock impl + ComplyAdvantage impl + `tests/contract/screening_contract.py` conformance suite | **Protocol + mock impl + tests against the mock only.** No second adapter; no shared conformance harness. |
| Tenant-scoped (`tenant_id` keyword arg on every fn) | **Single-tenant demo** — no `tenant_id`. Mirrors Stories 3.4 / 3.5 / 5.1. |
| `SCREENING_PROVIDER` env switches between `mock`/`complyadvantage` | **`SCREENING_PROVIDER` env exists** for the seam — only `mock` is implemented. Unknown provider raises `ValueError` (mirrors `_get_default_llm` in `apps/agents/src/agents/intake/document_intelligence.py`). |
| Sandbox API key + procurement runbook | **N/A** (cut entirely — no live vendor). |
| `name_match_score` from a real fuzzy match library | **`rapidfuzz.fuzz.token_set_ratio` / 100.0** — boring, deterministic, MIT-licensed. |

What survives: **`ScreeningRequest` / `ScreeningHit` / `ScreeningAdapter` Protocol in `packages/contracts/`, `MockScreeningAdapter` impl with deterministic fixtures, `get_default_screening_adapter()` factory, typed errors (`ScreeningTemporaryError` / `ScreeningPermanentError`), the `SCREENING_PROVIDER` env seam, the `agent_slug='screening'` matching `AgentSlug.SCREENING` from `contracts.agent_mesh`.**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` § Stories simplified, `architecture.md#Demo Scope Addendum (2026-04-29)` (resolved decision §1 "Screening vendor → mock-only"), and `architecture.md#Project-Specific Patterns` § P1 (Pluggable Adapter Pattern).

## Acceptance Criteria

1. **AC1 — Pydantic contracts in `packages/contracts/src/contracts/screening.py`.**

    ```python
    from datetime import date
    from typing import Literal

    from pydantic import BaseModel, Field

    from contracts.cases import CaseId
    from contracts.confidence import ConfidenceBand
    from contracts.provenance import ProvenancedField

    ScreeningCategory = Literal[
        "sanctions",
        "pep",
        "adverse_media",
        "law_enforcement",
        "watchlist",
    ]

    HitDisposition = Literal[
        "open",                # default — officer review pending
        "dismissed_by_agent",  # auto-filtered — see Story 6-2 AC
        "confirmed_by_officer",
        "dismissed_by_officer",
    ]


    class ScreeningSubject(BaseModel):
        """A single name+DOB+identifier triple to screen."""

        model_config = {"frozen": True}

        subject_kind: Literal["entity", "director", "ubo"]
        subject_id: str = Field(min_length=1)        # case-internal id (entity uuid, director ULID, UBO node id)
        full_name: str = Field(min_length=1, max_length=200)
        date_of_birth: date | None = None             # required for individuals; None for entity-kind
        identifiers: dict[str, str] = Field(default_factory=dict)
        # ^ optional id-document signals: e.g. {"pan": "ABCDE1234F"}, {"cin": "U12345MH..."}


    class ScreeningRequest(BaseModel):
        model_config = {"frozen": True}
        case_id: CaseId
        subjects: list[ScreeningSubject] = Field(min_length=1, max_length=50)


    class ScreeningHit(BaseModel):
        """One match from one subject against the vendor's index."""

        model_config = {"frozen": True}
        hit_id: str = Field(min_length=1)             # vendor-assigned id (mock prefixes "hit_mock_")
        subject_id: str = Field(min_length=1)          # mirrors ScreeningRequest.subjects[*].subject_id
        matched_name: str = Field(min_length=1, max_length=200)
        name_match_score: ProvenancedField[float]      # [0.0, 1.0]
        date_of_birth: date | None = None
        identifiers: dict[str, str] = Field(default_factory=dict)
        categories: list[ScreeningCategory] = Field(min_length=1)
        source_lists: list[str] = Field(default_factory=list)   # human-readable: "OFAC SDN", "RBI Wilful Defaulters"
        disposition: HitDisposition = "open"
        dismissal_rationale: str | None = None         # populated only when disposition == "dismissed_by_agent"
    ```

    Notes:
    * Wire format snake_case (architecture § Naming Patterns / Format Patterns).
    * `name_match_score` is wrapped in `ProvenancedField[float]` (P3) — `Provenance.source_agent="screening"`, `source_system="screening_mock"`, `confidence` equals `name_match_score.value`, `confidence_band=to_band(...)`, `evidence_ids=[]` (back-filled with the agent's own ledger ID per Story 5-1 / Story 3-4 pattern; that step happens in Story 6-2's supervisor integration, **not here**).
    * `dismissal_rationale` is populated by Story 6-2's auto-filter (the agent decides; the adapter doesn't pre-filter).
    * `model_config = {"frozen": True}` on every model — match Stories 5-1 / 5-3 frozen-aggregate convention.

2. **AC2 — `ScreeningAdapter` Protocol in the same module.**

    ```python
    from typing import Protocol


    class ScreeningTemporaryError(RuntimeError):
        """Vendor unreachable / rate-limited / 5xx — supervisor escalates with retry-marker."""


    class ScreeningPermanentError(RuntimeError):
        """Vendor 4xx (bad request, bad key, dropped subscription) — case blocks."""


    class ScreeningAdapter(Protocol):
        """All screening vendors implement this. Demo ships only the mock."""

        async def screen(self, req: ScreeningRequest) -> list[ScreeningHit]: ...
    ```

    No `tenant_id` keyword arg — single-tenant demo. The Protocol stays single-method (`screen`); per-subject batching is the adapter's internal concern.

3. **AC3 — Mock adapter at `apps/agents/src/agents/adapters/screening/mock.py`.**

    Folder layout (mirrors `apps/agents/src/agents/adapters/doc_ai/`):

    ```
    apps/agents/src/agents/adapters/screening/
    ├── __init__.py        # exports MockScreeningAdapter, get_default_screening_adapter
    ├── mock.py            # MockScreeningAdapter
    └── fixtures.py        # SCREENING_FIXTURES dict — deterministic data
    ```

    `MockScreeningAdapter` behaviour:

    * Reads from a static `SCREENING_FIXTURES: dict[tuple[str, date | None], list[_RawHit]]` keyed by (lowercased name, optional DOB). Returns deterministic results for the demo's three fixture cases (Vora, Shree, Ananya).
    * For unknown subjects, falls back to **fuzzy match** against the fixture's name corpus via `rapidfuzz.fuzz.token_set_ratio(subject.full_name, fixture_name) / 100.0`. Hits with score ≥ 0.50 are returned; otherwise no hit emitted for that subject.
    * `name_match_score.value` = the fuzz score in [0.0, 1.0]. For exact-key (case-insensitive) lookups, score is hard-coded in fixtures.
    * `hit_id` format: `hit_mock_<sha1(subject_id + matched_name)[:12]>` — deterministic across runs.
    * Does **not** set `disposition` → default `"open"`. Auto-dismissal is the agent's job (Story 6-2).
    * Async (`async def screen(...)`) but pure-Python — `await asyncio.sleep(0)` once at the top so the function genuinely yields, mirroring the doc-AI mock.
    * Raises **never** in the demo path. The error types exist on the Protocol so future real adapters can use them; the mock has no failure modes.

4. **AC4 — Fixture corpus in `apps/agents/src/agents/adapters/screening/fixtures.py`.**

    Three case-pinned hit sets — the demo's narrative depends on these:

    * **Vora Capital case** (`SHREE_VENKAT_ID` is the case ID for Shree's individual case; **Vora's case ID is `VORA_CAPITAL_ID` from `contracts.cases`**). Director "Patel R." (a UBO node from Story 5-3's seeded Vora graph) hits **OFAC SDN** with `name_match_score=0.73`, DOB mismatch (1961 vs 1978), category `["sanctions"]`. **This is the J1 demo's amber Screening hit.** Match this exactly — UX spec § J1 narrates "name 73% similar" verbatim.
    * **Shree Venkat case** — entity (Shree Venkat himself, individual-customer case): **no hits** (clean approval path).
    * **Ananya Iyer case** — Ananya hits **PEP** list with `name_match_score=0.88`, DOB match, category `["pep"]`, source list `"OpenSanctions Politicians"`. The demo's secondary J1 narrative (clean PEP confirmation).

    Fixture data lives in code, not JSON — frozen at import time, deterministic, easy to grep.

    The fixture entries reference **subject IDs from existing seed data**:
    * Vora's Patel R. director — read `apps/cockpit-api/scripts/seed_dev.py` for the exact UBO node ID; do not hand-roll a new one. The fixture must key on the subject_id the supervisor passes from the actual UBO graph.
    * Ananya Iyer — case has a single individual entity; `subject_id` will be the case's `customer_metadata.customer_id` (or `case_id` if no customer_id present — confirm via seed-data inspection during Task 4).

5. **AC5 — `get_default_screening_adapter()` factory in `apps/agents/src/agents/adapters/screening/__init__.py`.**

    ```python
    import os

    from contracts.screening import ScreeningAdapter
    from agents.adapters.screening.mock import MockScreeningAdapter


    def get_default_screening_adapter() -> ScreeningAdapter:
        provider = os.getenv("SCREENING_PROVIDER", "mock").lower()
        if provider == "mock":
            return MockScreeningAdapter()
        raise ValueError(
            f"Unknown SCREENING_PROVIDER={provider!r}. "
            f"Demo only implements 'mock'; ComplyAdvantage adapter deferred."
        )

    __all__ = [
        "MockScreeningAdapter",
        "get_default_screening_adapter",
    ]
    ```

    Mirrors the `_get_default_llm` shape in `apps/agents/src/agents/intake/document_intelligence.py`. Story 6-2 imports `get_default_screening_adapter` to resolve the adapter at agent-call time.

6. **AC6 — Re-export from `packages/contracts/src/contracts/__init__.py`.**

    Add to the public surface and `__all__`:
    `ScreeningAdapter`, `ScreeningCategory`, `ScreeningHit`, `ScreeningPermanentError`, `ScreeningRequest`, `ScreeningSubject`, `ScreeningTemporaryError`, `HitDisposition`. Keep alphabetical order in `__all__` (existing convention).

7. **AC7 — `rapidfuzz` dependency.**

    Add `rapidfuzz = "^3.9"` to `apps/agents/pyproject.toml` `[tool.poetry.dependencies]`. **Do not** add it to `packages/contracts` — the contracts package stays pure-Pydantic. The fuzzy match logic lives in the adapter (`apps/agents/`), not in the contract.

    `make agents-install` (or `cd apps/agents && poetry install`) after editing.

8. **AC8 — Tests at `apps/agents/tests/adapters/screening/test_mock.py`.**

    Cover:
    * **`screen` returns OFAC hit for Vora's Patel R. director with score 0.73 and category `["sanctions"]`** — exact narrative pin.
    * **`screen` returns no hit for Shree Venkat's entity** — clean path.
    * **`screen` returns PEP hit for Ananya Iyer with score 0.88 and DOB match** — happy-but-PEP path.
    * **Fuzzy fallback returns hit with score ≥ 0.50** — pass an unrecognized subject whose name is a near-miss; assert one hit at score in [0.50, 0.85].
    * **Fuzzy fallback returns no hit when score < 0.50** — pass "Zzzzz Nobody" with no DOB; assert empty list.
    * **`hit_id` is deterministic across two calls with the same input.**
    * **`name_match_score.provenance.source_agent == "screening"` and `source_system == "screening_mock"`.**
    * **`name_match_score.provenance.confidence_band == to_band(score)`.**

9. **AC9 — Tests at `packages/contracts/tests/test_screening.py`.**

    * `ScreeningRequest` rejects empty `subjects` list (`min_length=1`).
    * `ScreeningRequest` rejects > 50 subjects.
    * `ScreeningHit` rejects empty `categories` list.
    * `ScreeningHit.disposition` defaults to `"open"`.
    * `ScreeningHit` round-trips through `model_dump_json()` / `model_validate_json()` without loss — important for ledger persistence.
    * `ScreeningSubject` rejects `full_name` longer than 200 chars.

10. **AC10 — `get_default_screening_adapter` tests at `apps/agents/tests/adapters/screening/test_factory.py`.**

    * `get_default_screening_adapter()` returns `MockScreeningAdapter` when env unset.
    * `SCREENING_PROVIDER=mock` returns `MockScreeningAdapter`.
    * `SCREENING_PROVIDER=complyadvantage` raises `ValueError` with the demo-message text.
    * Use `monkeypatch.setenv` and `monkeypatch.delenv`, mirroring `apps/agents/tests/intake/test_document_intelligence.py` patterns.

11. **AC11 — `make lint && make test` clean.** Net-new test count: ≥ 8 in `test_mock.py`, ≥ 6 in `test_screening.py` (contracts), ≥ 3 in `test_factory.py`. No story modifies an agent — Story 6-2 wires this into the supervisor.

12. **AC12 — End-to-end smoke test.**

    ```bash
    poetry -C apps/agents run python -c "
    import asyncio
    from datetime import date
    from contracts.cases import VORA_CAPITAL_ID
    from contracts.screening import ScreeningRequest, ScreeningSubject
    from agents.adapters.screening import get_default_screening_adapter
    async def main():
        adapter = get_default_screening_adapter()
        req = ScreeningRequest(
            case_id=VORA_CAPITAL_ID,
            subjects=[ScreeningSubject(
                subject_kind='director', subject_id='ubo_patel_r_demo',
                full_name='Patel R.', date_of_birth=date(1978, 1, 1),
            )],
        )
        hits = await adapter.screen(req)
        assert any(h.matched_name.startswith('Patel') and 'sanctions' in h.categories for h in hits), hits
        print('OK', len(hits), 'hit(s)')
    asyncio.run(main())
    "
    ```

    Should print `OK 1 hit(s)` (or more, if Vora's other directors are also in the fixture). Exit zero. The exact `subject_id` string above is illustrative — match what the supervisor will pass after consulting the real UBO graph (see AC4 note).

## Tasks / Subtasks

- [x] **Task 1 — Pydantic contracts** (AC: #1, #2, #6, #9)
  - [x] Subtask 1.1 — `packages/contracts/src/contracts/screening.py` with `ScreeningSubject`, `ScreeningRequest`, `ScreeningHit`, `ScreeningAdapter` Protocol, `ScreeningTemporaryError`, `ScreeningPermanentError`, `ScreeningCategory`, `HitDisposition`.
  - [x] Subtask 1.2 — Re-export from `packages/contracts/src/contracts/__init__.py` (alphabetical `__all__`).
  - [x] Subtask 1.3 — `packages/contracts/tests/test_screening.py` (8 cases).
  - [x] Subtask 1.4 — Run `make contracts` to regenerate `apps/cockpit-ui/src/api-types.ts`.

- [x] **Task 2 — `rapidfuzz` dependency** (AC: #7)
  - [x] Subtask 2.1 — `apps/agents/pyproject.toml` `[tool.poetry.dependencies]` adds `rapidfuzz = "^3.9"`.
  - [x] Subtask 2.2 — `cd apps/agents && poetry lock --no-update && poetry install`.

- [x] **Task 3 — Mock adapter** (AC: #3, #5, #8, #10)
  - [x] Subtask 3.1 — `apps/agents/src/agents/adapters/screening/__init__.py` with `get_default_screening_adapter`.
  - [x] Subtask 3.2 — `apps/agents/src/agents/adapters/screening/mock.py` with `MockScreeningAdapter`.
  - [x] Subtask 3.3 — `apps/agents/tests/adapters/screening/test_factory.py` (4 cases).
  - [x] Subtask 3.4 — `apps/agents/tests/adapters/screening/test_mock.py` (9 cases).

- [x] **Task 4 — Fixture corpus** (AC: #4)
  - [x] Subtask 4.1 — Read `apps/cockpit-api/scripts/seed_dev.py` + `apps/agents/src/agents/tools/mca_mock.py` to lock UBO subject IDs (Vora directors via DIN → `ubo_p_<din>`; Ananya via case_id; Shree clean).
  - [x] Subtask 4.2 — `apps/agents/src/agents/adapters/screening/fixtures.py` with `SCREENING_FIXTURES` dict + `SUBJECT_ID_OVERRIDES` + `FUZZY_CORPUS`.
  - [x] Subtask 4.3 — Tests at AC8 use these exact subject_id values.

- [x] **Task 5 — Verification** (AC: #11, #12)
  - [x] Subtask 5.1 — `make lint` clean; all Python tests green (193 contracts + 141 cockpit-api + 121 agents). Pre-existing Vitest failures in `useCases.test.tsx` / `useCase.test.tsx` reproduce on clean main (unrelated to this story).
  - [x] Subtask 5.2 — Manual smoke per AC12 prints `OK 1 hit(s)` for Vora's Rohan Mehta director.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Project-Specific Patterns` § P1 Pluggable Adapter Pattern] Protocol + at-least-one impl + factory; second-impl conformance test deferred for demo per Demo Scope Addendum row "Vendor adapters → mock-only".
* [Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Resolved open architectural decisions] Decision §1 "Screening vendor selection → Mock-only. No live vendor."
* [Source: `architecture.md#Project-Specific Patterns` § P3 Provenance Metadata Pattern] `name_match_score` wrapped in `ProvenancedField[float]`. `evidence_ids=[]` here; supervisor back-fills in Story 6-2 (mirrors Story 5-1 § AC8 entity-verification two-pass).
* [Source: `architecture.md#Format Patterns`] Wire enum values are snake_case (`dismissed_by_agent`, not `DismissedByAgent`). Empty list → `[]`, never `null`.
* [Source: `architecture.md#Naming Patterns`] Python files snake_case; the registry slug `screening` matches `AgentSlug.SCREENING = "screening"` from `contracts.agent_mesh`.
* [Source: `prd.md#Functional Requirements § Screening & Risk Analysis` FR18] "The Screening agent can evaluate case entities and associated individuals against the configured screening vendor and surface hits with match details." This story is the **adapter** under FR18 — the agent itself is Story 6-2.

### Critical pitfalls

1. **Don't put `rapidfuzz` in `packages/contracts`.** The contracts package is the source-of-truth Pydantic schemas with no runtime libraries. Fuzzy match is adapter-side. `packages/contracts` only adds Pydantic models.

2. **`ScreeningAdapter` is a `Protocol`, not an `ABC`.** Match the existing pattern in `packages/contracts/src/contracts/mca.py` (`MCALookup` is a `Protocol`). `Protocol` keeps the adapter loosely coupled — implementations don't inherit, they structurally conform.

3. **`subject_id` is a `str`, not a typed alias.** Subjects come from heterogeneous sources (entity uuid, UBO node id, director id from Document Intelligence). A `str` keeps it open-ended; the agent + supervisor coordinate on actual format. Don't introduce a `SubjectId = Annotated[str, ...]` alias — premature constraint.

4. **`name_match_score` provenance.confidence equals the score itself, not a separately computed agent confidence.** The mock's "confidence in this hit" is exactly the fuzzy match score. For real vendors, this would diverge. Document this in a code comment; it surfaces in test assertions.

5. **Fixture subject_ids must match what the supervisor will pass in Story 6-2.** Read seed_dev.py first; otherwise the AC4 fixture works in tests but doesn't fire in the demo. This is the most likely "tests pass but demo broken" trap.

6. **Don't pre-filter low-score hits in the adapter.** Auto-dismissal is the agent's job per Story 6-2's `dismissed_by_agent` flow. The adapter returns everything ≥ 0.50 (the noise floor for the fuzzy fallback); the agent decides what to surface.

7. **`SCREENING_PROVIDER` env unset → defaults to `mock`.** Don't crash if env missing — the demo's default makes runs trivial. `make dev` and `make test` should both work without setting it.

8. **`packages/contracts/tests/test_screening.py` uses pytest, not Vitest.** Match the existing test style under `packages/contracts/tests/` (e.g., `test_entity_verification.py`); no `unittest.TestCase` subclasses.

### Story dependencies

* **Strict prereqs:** `packages/contracts.cases` (CaseId, fixture IDs), `packages/contracts.confidence` (`ConfidenceBand`, `to_band`), `packages/contracts.provenance` (`ProvenancedField`, `Provenance`), `packages/contracts.agent_mesh` (`AgentSlug.SCREENING` already enumerated).
* **Read by:** Story 6-2 (Screening agent imports `get_default_screening_adapter`, `ScreeningRequest`, `ScreeningHit`); Story 6-3 (TS types regenerated from contracts); Story 6-4 (ReasoningTrace contract uses the Provenance pattern from this story as reference).
* **Reads from:** Story 3-3 (Provenance contract — already exists); Story 3-4 (`apps/agents/src/agents/intake/document_intelligence.py` adapter factory pattern).

### Project Structure Notes

This story creates:
- `packages/contracts/src/contracts/screening.py`
- `packages/contracts/tests/test_screening.py`
- `apps/agents/src/agents/adapters/screening/__init__.py`
- `apps/agents/src/agents/adapters/screening/mock.py`
- `apps/agents/src/agents/adapters/screening/fixtures.py`
- `apps/agents/tests/adapters/screening/__init__.py` (empty)
- `apps/agents/tests/adapters/screening/test_mock.py`
- `apps/agents/tests/adapters/screening/test_factory.py`

This story modifies:
- `packages/contracts/src/contracts/__init__.py` — public exports
- `apps/agents/pyproject.toml` — add `rapidfuzz`
- `apps/agents/poetry.lock` (regenerated)

This story DOES NOT create:
- The Screening agent (Story 6-2)
- The cockpit-api `/v1/agents/screening/run` route (Story 6-2's responsibility — the agent's @ledgered_action wraps the adapter call; this story's tests call the adapter directly)
- A Story 6-2 supervisor entry in `INTAKE_AGENTS` (Story 6-2)
- A second screening vendor adapter (cut from demo scope)
- A separate conformance test harness (cut)

### References

- [Source: `epics.md#Epic 6` § Story 6.1] original AC (re-scoped here — drops the conformance suite phrasing, drops the tenant_id scoping)
- [Source: `architecture.md#Project-Specific Patterns`] § P1 (Pluggable Adapter), § P3 (Provenance), § P7 (Confidence Banding)
- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] resolved decision §1
- [Source: `prd.md#Functional Requirements § Screening & Risk Analysis`] FR18
- [Source: `prd.md#Risk Mitigations`] "Screening vendor lock-in → Pluggable adapter from day 1"
- [Source: `5-1-entity-verification-agent.md` § AC1, AC10] Provenance + `to_band` + `evidence_ids=[]` two-pass pattern
- [Source: `apps/agents/src/agents/intake/document_intelligence.py` § `_get_default_llm`] adapter factory shape this story mirrors

### Demo verification protocol

```bash
make lint && make test
poetry -C apps/agents run python -c "$(cat <<'PY'
import asyncio
from datetime import date
from contracts.cases import VORA_CAPITAL_ID
from contracts.screening import ScreeningRequest, ScreeningSubject
from agents.adapters.screening import get_default_screening_adapter

async def main():
    adapter = get_default_screening_adapter()
    req = ScreeningRequest(
        case_id=VORA_CAPITAL_ID,
        subjects=[ScreeningSubject(
            subject_kind='director', subject_id='<from seed_dev.py>',
            full_name='Patel R.', date_of_birth=date(1978, 1, 1),
        )],
    )
    hits = await adapter.screen(req)
    assert any(h.matched_name.lower().startswith('patel') and 'sanctions' in h.categories for h in hits), hits
    print('OK', len(hits), 'hit(s)')
asyncio.run(main())
PY
)"
```

If any step fails, the bug is in this story; do not ship until green.

## Dev Agent Record

### Agent Model Used

(claude-opus-4-7 + Amelia persona, bmad-dev-story workflow)

### Debug Log References

- Pre-existing Vitest failures in `apps/cockpit-ui/src/hooks/useCases.test.tsx` (2 tests) and `useCase.test.tsx` (3 tests) reproduce on clean `main` (verified via `git stash` round-trip). Not caused by Story 6.1 work; tracked as a separate UI test-harness regression.

### Completion Notes List

- **Deviation from AC #4 narrative**: original AC text references a "Patel R." director on Vora's UBO graph, but the seeded MCA data (`apps/agents/src/agents/tools/mca_mock.py`) lists Devansh Vora, Rohan Mehta, and A K Filing Services — there is no "Patel R." director. Pinned the OFAC SDN hit to **Rohan Mehta** (DIN `09876544` → subject_id `ubo_p_09876544`); kept the OFAC record's `matched_name` as "Patel R." so the J1 narrative ("name 73% similar") still reads correctly (the watchlist record name differs from the subject name — that IS the 73% partial match). Documented in `fixtures.py` module docstring.
- **Subject ID resolution for Ananya**: Story 6.1 AC #4 says "subject_id will be the case's customer_metadata.customer_id (or case_id if no customer_id present)". Ananya's `customer_metadata.extra` has no `customer_id` key, so the fixture keys on `ANANYA_IYER_ID` directly via `SUBJECT_ID_OVERRIDES`. The supervisor in Story 6.2 will pass the case_id when the case is `customer_type=individual`.
- **`SUBJECT_ID_OVERRIDES` map added** alongside the AC-mandated `(name, dob)` keying. Reason: individual cases are screened via case_id (no UBO graph), so name-only lookup couldn't disambiguate. Both lookup paths are deterministic; tests cover both.
- **Fuzzy fallback** uses `rapidfuzz.fuzz.token_set_ratio / 100.0` per AC #3, threshold 0.50. Falls back through both name and DOB-keyed corpus rows so token-permuted names ("Mehta Rohan") still resolve.
- **No agent.yaml in this story** — registration to IBM Orchestrate happens in Story 6.2 when the Screening agent itself ships. This story is the contract + adapter only.

### File List

- `packages/contracts/src/contracts/screening.py` (new) — Pydantic contracts + Protocol + error types.
- `packages/contracts/src/contracts/__init__.py` (modified) — re-export screening symbols.
- `packages/contracts/tests/test_screening.py` (new) — 8 contract tests.
- `apps/agents/pyproject.toml` (modified) — added `rapidfuzz = "^3.9"`.
- `apps/agents/poetry.lock` (regenerated).
- `apps/agents/src/agents/adapters/screening/__init__.py` (new) — `get_default_screening_adapter` factory.
- `apps/agents/src/agents/adapters/screening/mock.py` (new) — `MockScreeningAdapter`.
- `apps/agents/src/agents/adapters/screening/fixtures.py` (new) — `SCREENING_FIXTURES`, `SUBJECT_ID_OVERRIDES`, `FUZZY_CORPUS`.
- `apps/agents/tests/adapters/__init__.py` (new) — empty.
- `apps/agents/tests/adapters/screening/__init__.py` (new) — empty.
- `apps/agents/tests/adapters/screening/test_mock.py` (new) — 9 adapter tests.
- `apps/agents/tests/adapters/screening/test_factory.py` (new) — 4 factory tests.
- `packages/contracts/openapi.json` (regenerated by `make contracts`).
- `apps/cockpit-ui/src/api-types.ts` (regenerated by `make contracts`).

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-08 | Story 6.1 drafted. Demo replacement for bank-buyer Stories 6.1 + 6.2: `ScreeningAdapter` Protocol + `MockScreeningAdapter` + fixtures pinned to demo cases (Vora OFAC 73%, Shree clean, Ananya PEP 88%); ComplyAdvantage impl and conformance suite cut per re-scope. |
| 2026-05-08 | Implemented Story 6.1. Contracts + Protocol + `MockScreeningAdapter` with deterministic exact-key + subject-id-override + fuzzy fallback. 21 net-new tests (8 contracts + 9 adapter + 4 factory) all passing; `make lint` clean; AC12 smoke prints `OK 1 hit(s)`. Pinned OFAC SDN hit to Rohan Mehta (`ubo_p_09876544`) instead of fictional "Patel R." director (the watchlist record name is "Patel R." — partial namesake). |
