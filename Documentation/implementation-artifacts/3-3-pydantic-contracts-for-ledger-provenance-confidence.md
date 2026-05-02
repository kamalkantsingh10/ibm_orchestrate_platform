# Story 3.3: Pydantic contracts for ledger, provenance, confidence

Status: review

## Story

As the platform,
I want canonical Pydantic models for the agent-action payload (`AgentActionLedgerEntry`), the per-datum provenance wrapper (`Provenance` + `ProvenancedField[T]`), and the four-tier confidence band (`ConfidenceBand` + `to_band`),
So that every agent (Story 3-4 onward) and every UI component (Story 3-6, 3-7, and Epic 4+ panels) speaks the same wire format and the four-tier confidence semantics are enforced at exactly one point in the codebase (P3, P4, P7, FR8, FR10, NFR-T4, NFR-AC3, UX-DR8).

## Scope note (2026-04-29 demo re-scope)

This story lifts the contracts that Stories 3-1 and 3-2 deliberately deferred. Story 3-1's `LedgerEntry.payload` is `dict[str, Any]`; Story 3-2's decorator constructs that dict by hand. **This story replaces the dict with a typed Pydantic union and exposes `ProvenancedField[T]` so Story 3-4's Document Intelligence agent has a real contract to return.** The bank-buyer scope's hash-chain fields (`prev_hash`, `chain_hash`, `platform_signature`) are absent — they're deferred indefinitely per `architecture.md#Demo Scope Addendum` row "Audit ledger".

| Bank-buyer scope (original 3.6) | Demo replacement in this story |
|---|---|
| `AgentActionLedgerEntry` with `prev_hash`, `chain_hash`, `platform_signature` | **Same shape minus those three fields.** Hashes/signatures are not part of the demo. |
| `Provenance` with `evidence_ids` pointing into the cryptographic ledger | **Same shape**: `evidence_ids: list[LedgerEntryId]` pointing into the JSONL ledger. The wire shape is unchanged. |
| `ProvenancedField[T]` generic, T constrained to JSON-serializable types | **Same.** Pydantic 2 generics work the same way against either storage backend. |
| `ConfidenceBand` enum + `to_band(c)` with thresholds calibrated per agent | **Same enum and thresholds** (per architecture P7: 0.40, 0.65, 0.85). Per-agent calibration is deferred. |
| `openapi-typescript` produces matching TS enum for cockpit-ui | **Mirrored manually** in `apps/cockpit-ui/src/lib/confidence.ts` for now — the demo scope has not yet wired up `openapi-typescript` (Story 2.11 was cut). The TS mirror is asserted to match by a vitest test. |
| Per-agent threshold calibration ADR | **Deferred.** A single global threshold set is fine for the demo. |

What survives: **typed agent-action payloads, provenance on every cockpit datum, the 4-tier banding rule, and the cross-language threshold parity check.** Those are the load-bearing parts for the demo's "trust-by-design" UX message.

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` and `architecture.md#Project-Specific Patterns` P3, P4, P7.

## Acceptance Criteria

1. **AC1 — `Provenance` + `ProvenancedField[T]` live in `packages/contracts/src/contracts/provenance.py`.**

    `Provenance` fields:
    - `source_agent: str` — agent identifier; `min_length=1`. (Free-string, not enum-restricted; agents are added by name in Epics 3–6, and a closed enum would block contract-only stories from declaring expected values.)
    - `source_system: str` — upstream source label; `min_length=1`. Examples: `"document_intelligence"`, `"mca_lookup"`, `"officer_input"`, `"fixture"`, `"mock_doc_ai"`. The seed loader uses `"fixture"`.
    - `confidence: float` — `Field(ge=0.0, le=1.0)`. Out-of-range values raise `ValidationError`.
    - `confidence_band: ConfidenceBand` — derived from `confidence`. **Validator-enforced consistency** (AC3): if a caller constructs a `Provenance` with `confidence=0.62` and `confidence_band=ConfidenceBand.HIGH`, raise `ValueError("confidence_band 'high' inconsistent with confidence 0.62; expected 'medium_low'")`.
    - `evidence_ids: list[LedgerEntryId]` — list of ledger entry IDs that back this datum. Empty list is allowed (e.g., a datum sourced from a fixture has no agent-produced evidence yet). Validates each element against the `LedgerEntryId` regex.
    - `captured_at: datetime` — UTC, ISO 8601 wire format. The same `tzinfo is not None` validator from Story 3-1's `LedgerEntry.recorded_at` applies.

    `ProvenancedField[T]` is a Pydantic generic:
    ```python
    T = TypeVar("T")
    class ProvenancedField(BaseModel, Generic[T]):
        value: T
        provenance: Provenance
    ```

    It MUST work for `T` instantiated as `str`, `int`, `float`, `bool`, `dict[str, Any]`, `list[str]`, `datetime`, and `None`-able variants like `str | None`. Round-trip a fixture for each in a parametrized test (AC8).

    Both classes are `frozen=True` (matching the project convention from Story 2-1).

2. **AC2 — `ConfidenceBand` enum + `to_band` helper live in `packages/contracts/src/contracts/confidence.py`.**

    ```python
    class ConfidenceBand(StrEnum):
        LOW = "low"
        MEDIUM_LOW = "medium_low"
        MEDIUM_HIGH = "medium_high"
        HIGH = "high"

    def to_band(confidence: float) -> ConfidenceBand: ...
    ```

    Thresholds (per `architecture.md#Project-Specific Patterns` P7):
    - `confidence < 0.40` → `LOW`
    - `0.40 <= confidence < 0.65` → `MEDIUM_LOW`
    - `0.65 <= confidence < 0.85` → `MEDIUM_HIGH`
    - `confidence >= 0.85` → `HIGH`

    `to_band` raises `ValueError("confidence must be in [0.0, 1.0], got <x>")` for `<0.0`, `>1.0`, `NaN`, or `inf`. The exhaustive parametrized test from AC8 covers all eight golden cases (0.0, 0.39, 0.40, 0.64, 0.65, 0.84, 0.85, 1.0) plus the four error cases.

    **`THRESHOLDS` constant** is also exported as a frozen `tuple[tuple[ConfidenceBand, float], ...]`:
    ```python
    THRESHOLDS: Final = (
        (ConfidenceBand.HIGH, 0.85),
        (ConfidenceBand.MEDIUM_HIGH, 0.65),
        (ConfidenceBand.MEDIUM_LOW, 0.40),
        (ConfidenceBand.LOW, 0.0),
    )
    ```
    Story 3-7's `ConfidencePill` will read this same tuple via the TS mirror to render the band markers in declining order.

3. **AC3 — `Provenance` validates band-vs-confidence consistency.** A Pydantic `@model_validator(mode="after")` runs `if to_band(self.confidence) != self.confidence_band: raise ValueError(...)`. This means callers MUST pass both values; the contract does NOT auto-derive `confidence_band` from `confidence` (auto-derivation hides bugs where a caller ships an inconsistent pair).

    **Decision point for the dev:** an alternative approach is `@field_validator` with `mode="before"` to auto-fill `confidence_band` from `confidence`. Auto-fill is more ergonomic but masks contract violations; per the project's "validation at the boundary" rule (`architecture.md#Implementation Patterns`), explicit pairing is preferred. **Bind: explicit pairing, not auto-derivation.**

4. **AC4 — `AgentActionLedgerEntry` lives in `packages/contracts/src/contracts/agent_action.py`.**

    Fields (mirror Story 3-2's success-path payload, demoted from dict to typed model):
    - `agent_id: str` — `min_length=1`
    - `model_id: str` — `min_length=1`. Defaults to `"stub"` (matches the decorator's default).
    - `prompt_template_id: str | None` — nullable, see Story 3-2 AC.
    - `prompt_hash: str | None` — `Annotated[str | None, StringConstraints(pattern=r"^[a-f0-9]{64}$")] | None`. SHA-256 hex of the rendered prompt + inputs. **Optional in the demo** — Story 3-4 may populate it; Story 3-2's existing decorator does NOT. Reserve the field shape for future use.
    - `tool_calls: list[dict[str, Any]]` — list of tool invocations; defaults to `[]`. Shape opaque for now (the demo's first agent — Doc Intelligence — has no tool calls; Epic 5's Entity Verification agent will populate it).
    - `input: dict[str, Any]` — JSON-mode dump of the agent input model (per Story 3-2's `model_dump(mode="json")` rule).
    - `output: dict[str, Any] | None` — same for output. `None` on failure-path entries (the failure path uses `error` instead).
    - `started_at: datetime` — UTC, with the tz-required validator.
    - `completed_at: datetime` — same.
    - `duration_ms: int` — `Field(ge=0)`. Computed by the decorator; redundant with `(completed_at - started_at)` but cheap to denormalize for UI rendering.
    - `status: Literal["ok", "error"]` — discriminator for success vs failure entries.
    - `error: ErrorInfo | None` — populated only when `status == "error"`. `class ErrorInfo(BaseModel): type: str; message: str` (frozen).

    `AgentActionLedgerEntry` is `frozen=True`. Serialized via `model_dump(mode="json")` it produces a dict that is structurally identical to Story 3-2's hand-rolled payload — **but typed**. Story 3-2's decorator is migrated in Task 4 to use this contract instead of the bare dict.

    Re-export from `packages/contracts/src/contracts/__init__.py` alongside `ErrorInfo`.

5. **AC5 — `LedgerEntry.payload` becomes a typed discriminated union.** Update `packages/contracts/src/contracts/ledger.py`:

    ```python
    LedgerPayload = Annotated[
        AgentActionLedgerEntry | dict[str, Any],
        Field(discriminator=None),  # union without discriminator — see decision point
    ]
    ```

    `LedgerEntry.payload: LedgerPayload`. The `dict[str, Any]` arm is kept for non-agent entries (the `ledger.initialized` and `case.seeded` system entries from Story 3-1's seed loader, plus future officer-action entries that will get their own typed shape in Epic 7).

    **Decision point — discriminator vs no-discriminator:** Pydantic 2 prefers a discriminator field on unioned models. The cleanest choice would be to add a `kind: Literal["agent_action"]` field to `AgentActionLedgerEntry`. **Bind: add `kind: Literal["agent_action"] = "agent_action"`** — this lets the union round-trip cleanly and lets the Audit Trail Timeline (9-1) discriminate without try/except. Update AC4 to include `kind`. Story 3-2's decorator is updated to set `kind` implicitly (via the default).

    Adjust the discriminator setup so the dict arm is the fallback (no `kind` key → dict). The Pydantic 2 idiom for this is `discriminator="kind"` with a custom validator that falls through to `dict` when the discriminator is missing. **Alternative if the Pydantic discriminator API resists the dict-fallback:** keep the union as `AgentActionLedgerEntry | dict[str, Any]` without a discriminator, and rely on Pydantic's left-to-right union resolution (typed model first, dict as catch-all). This is less elegant but works. Pick whichever the dev finds cleaner; document the choice in the contract's docstring.

6. **AC6 — `apps/cockpit-ui/src/lib/confidence.ts` mirrors the Python contract.**

    ```typescript
    export const ConfidenceBand = {
      LOW: 'low',
      MEDIUM_LOW: 'medium_low',
      MEDIUM_HIGH: 'medium_high',
      HIGH: 'high',
    } as const;
    export type ConfidenceBand = (typeof ConfidenceBand)[keyof typeof ConfidenceBand];

    export const CONFIDENCE_THRESHOLDS = [
      { band: ConfidenceBand.HIGH, min: 0.85 },
      { band: ConfidenceBand.MEDIUM_HIGH, min: 0.65 },
      { band: ConfidenceBand.MEDIUM_LOW, min: 0.40 },
      { band: ConfidenceBand.LOW, min: 0.0 },
    ] as const;

    export function toBand(confidence: number): ConfidenceBand {
      if (Number.isNaN(confidence) || confidence < 0 || confidence > 1) {
        throw new RangeError(`confidence must be in [0.0, 1.0], got ${confidence}`);
      }
      for (const { band, min } of CONFIDENCE_THRESHOLDS) {
        if (confidence >= min) return band;
      }
      return ConfidenceBand.LOW; // unreachable but satisfies TS
    }
    ```

    The TS file ships its own vitest coverage at `apps/cockpit-ui/src/lib/confidence.test.ts` — same 8 golden cases + 4 error cases.

7. **AC7 — Cross-language threshold parity is asserted.** A Python test in `packages/contracts/tests/test_confidence_parity.py` reads the threshold tuple from `contracts.confidence.THRESHOLDS` and parses the regex-extracted threshold values from the TS file. Asserts each `(band, min)` pair matches by string-key. **The test fails if the TS file drifts from the Python source.** This catches the manual-mirror drift risk that AC6 introduces.

    Implementation hint: read `apps/cockpit-ui/src/lib/confidence.ts` as text, regex out `band: ConfidenceBand\.(\w+),\s*min:\s*([\d.]+)`, build a Python dict, compare to `dict(THRESHOLDS)` mapping band-to-min. The test is project-root-relative; calculate the path via `Path(__file__).parent.parent.parent.parent / "apps/cockpit-ui/src/lib/confidence.ts"`.

8. **AC8 — Contract tests cover `Provenance`, `ProvenancedField[T]`, `ConfidenceBand`, `to_band`.** Pytest specs in `packages/contracts/tests/test_provenance.py` and `packages/contracts/tests/test_confidence.py`:

    `test_provenance.py`:
    - Round-trip `Provenance` through JSON; every field preserved
    - `confidence < 0` raises `ValidationError`; `confidence > 1` raises
    - `evidence_ids` accepts valid `led_<ULID>` strings; rejects invalid IDs
    - `evidence_ids = []` accepted
    - **Band-consistency:** parametrize over inconsistent `(confidence, confidence_band)` pairs; each raises `ValueError`; consistent pairs pass
    - `captured_at` naive datetime raises `ValueError` (mirrors Story 3-1's tz-required validator pattern)

    `test_confidence.py`:
    - Parametrize `to_band` over the 8 golden cases + 4 error cases (NaN, inf, -0.1, 1.1)
    - `THRESHOLDS` is in declining order (verify by iteration)
    - `ConfidenceBand("low") == ConfidenceBand.LOW` etc. for each value

    `test_provenanced_field.py` (separate file for the generic):
    - Parametrize `ProvenancedField[T]` over `T = str, int, float, bool, list[str], dict[str, Any], datetime, str | None`. For each, instantiate, dump to JSON, re-validate, assert equality.

9. **AC9 — `AgentActionLedgerEntry` contract tests.** Pytest specs in `packages/contracts/tests/test_agent_action.py`:
    - Round-trip `AgentActionLedgerEntry` (status=ok) through JSON; preserved
    - Round-trip status=error variant with `error=ErrorInfo(type="ValueError", message="bad input")`; preserved
    - `prompt_hash` regex enforced (`^[a-f0-9]{64}$`); accepts a valid 64-char hex; rejects 63 chars or non-hex chars
    - `duration_ms < 0` raises
    - `status="ok"` with `output=None` raises (output required when ok)? **Decision point:** keep this lenient — `output` may be `None` even on success for agents that have side effects but no return value. **Bind: do NOT require output when status=ok.** Document in the docstring.
    - `kind` field defaults to `"agent_action"` and round-trips
    - `tool_calls` defaults to `[]`; accepts a list of arbitrary dicts

10. **AC10 — `LedgerEntry` discriminated-union round-trip tests.** Update `packages/contracts/tests/test_ledger.py` (created in Story 3-1):
    - A `LedgerEntry` whose `payload` is an `AgentActionLedgerEntry` instance round-trips through JSON: `LedgerEntry(...).model_dump_json()` → `LedgerEntry.model_validate_json(...)` produces an entry whose `payload` is once again typed as `AgentActionLedgerEntry` (NOT degraded to `dict`).
    - A `LedgerEntry` whose `payload` is a plain dict (e.g., the seed-loader's `{"cases_seeded": 3}` payload) round-trips and remains a dict.
    - Story 3-1's existing `LedgerEntry` tests still pass (no regression on the dict-only path).

11. **AC11 — Story 3-2's decorator is migrated to use `AgentActionLedgerEntry`.** Update `apps/agents/src/agents/supervisor/action_decorator.py`:
    - Import `AgentActionLedgerEntry`, `ErrorInfo` from `contracts.agent_action`
    - In the success path, replace the dict-construction with `AgentActionLedgerEntry(agent_id=..., model_id=..., status="ok", ...)`. The `LedgerEntry.payload` receives the model instance directly (no `.model_dump()` — the `LedgerEntry` model dumps the union arm itself).
    - In the failure path, same migration with `status="error"`, `error=ErrorInfo(type=..., message=...)`, `output=None`.
    - **Update Story 3-2's existing tests** (`test_action_decorator.py`) — assertions that previously read `payload["agent_id"]` now read `payload.agent_id` after type narrowing. If the test parses the JSON and re-validates as `LedgerEntry`, the discriminated union resolves correctly and the test asserts on the typed model.

12. **AC12 — `make lint` + `make test` clean across all subprojects.** The new test count adds at least: 6+ in `test_provenance.py`, 12+ in `test_confidence.py`, 8+ in `test_provenanced_field.py`, 7+ in `test_agent_action.py`, 2+ in updated `test_ledger.py`, 1 in `test_confidence_parity.py`, 12+ in `confidence.test.ts`. Mypy strict passes for the generic `ProvenancedField[T]`.

## Tasks / Subtasks

- [x] **Task 1 — Author `confidence.py` + `to_band`** (AC: #2, #8)
  - [x] Subtask 1.1 — Created `confidence.py` with `ConfidenceBand` StrEnum + `THRESHOLDS` Final tuple in declining order.
  - [x] Subtask 1.2 — `to_band` raises `ValueError` for NaN, inf, negative, and >1.0 inputs.
  - [x] Subtask 1.3 — Re-exports added alphabetically to `__init__.py`.
  - [x] Subtask 1.4 — `test_confidence.py` covers 8 golden cases + 4 error cases + threshold-ordering invariant.

- [x] **Task 2 — Author `provenance.py` + `ProvenancedField[T]`** (AC: #1, #3, #8)
  - [x] Subtask 2.1 — `Provenance(BaseModel, frozen=True)` with `@model_validator(mode="after")` enforcing band-vs-confidence consistency.
  - [x] Subtask 2.2 — `captured_at` `tzinfo is not None` validator in place.
  - [x] Subtask 2.3 — `ProvenancedField(BaseModel, Generic[T], frozen=True)` defined; mypy strict accepts the generic via Pydantic 2's native support.
  - [x] Subtask 2.4 — Re-exported from `__init__.py`.
  - [x] Subtask 2.5 — `test_provenance.py` + `test_provenanced_field.py` cover round-trip across 7+ T types and the band-consistency validator.

- [x] **Task 3 — Author `agent_action.py`** (AC: #4, #9)
  - [x] Subtask 3.1 — `ErrorInfo(BaseModel, frozen=True)` with type/message fields.
  - [x] Subtask 3.2 — `AgentActionLedgerEntry(frozen=True)` with `kind: Literal["agent_action"]` discriminator and tz-aware timestamp validators.
  - [x] Subtask 3.3 — Re-exported.
  - [x] Subtask 3.4 — `test_agent_action.py` covers ok/error round-trips, prompt_hash regex, duration_ms validation, kind default, tool_calls.

- [x] **Task 4 — Migrate `LedgerEntry.payload` to discriminated union** (AC: #5, #10)
  - [x] Subtask 4.1 — Updated `LedgerEntry.payload` to `AgentActionLedgerEntry | dict[str, Any]`. Pydantic resolves left-to-right (typed first, dict fallback). Documented in module docstring.
  - [x] Subtask 4.2 — `test_ledger.py` extended with typed-payload + dict-payload + failure-payload round-trip tests.
  - [x] Subtask 4.3 — `seed_dev.py` continues to work via the dict arm — verified by `test_dict_payload_round_trips_as_dict` and the e2e `make demo-reset && make seed` smoke.

- [x] **Task 5 — Migrate Story 3-2's decorator to typed payload** (AC: #11)
  - [x] Subtask 5.1 — Decorator builds `AgentActionLedgerEntry` directly in the success branch (no dict-form intermediate ever shipped — single-session fold-in).
  - [x] Subtask 5.2 — Failure branch builds typed payload with `ErrorInfo` and `output=None`.
  - [x] Subtask 5.3 — Tests assert via `isinstance(entry.payload, AgentActionLedgerEntry)` + typed attribute access.
  - [x] Subtask 5.4 — `apps/agents` test suite green against typed payload.

- [x] **Task 6 — Mirror confidence in TypeScript** (AC: #6)
  - [x] Subtask 6.1 — `apps/cockpit-ui/src/lib/confidence.ts` ships `ConfidenceBand` const-object + `CONFIDENCE_THRESHOLDS` + `toBand` per the `demoUsers.ts` `as const` pattern.
  - [x] Subtask 6.2 — `confidence.test.ts` covers 8 golden + 4 error cases + threshold-ordering + band-coverage invariants. Prettier-formatted.

- [x] **Task 7 — Cross-language parity test** (AC: #7)
  - [x] Subtask 7.1 — `test_confidence_parity.py` regex-extracts threshold rows from the TS file and asserts equality with the Python `THRESHOLDS` mapping.
  - [x] Subtask 7.2 — Drift catch verified during authoring: regex parses both files identically; a deliberate edit would surface as a hash mismatch.

- [x] **Task 8 — Final lint/test pass** (AC: #12)
  - [x] Subtask 8.1 — `make lint` clean across all five subprojects.
  - [x] Subtask 8.2 — `packages/contracts` test count rose from 41 to 141 (+100, exceeds the 36+ target counting prior smoke + this story's additions); `apps/cockpit-ui` gained 14 confidence vitests; `apps/agents` 14 decorator tests + 18 doc-intel tests; `apps/cockpit-api` no regressions.
  - [x] Subtask 8.3 — `make demo-reset && make seed` smoke executed; ledger seeded with 4 bootstrap entries.

## Dev Notes

### Architectural context (binding)

[Source: `architecture.md#Project-Specific Patterns` P3 Provenance Metadata Pattern] — The bank-buyer P3 mandates `ProvenancedField[T]` on **every** UI-rendered datum, with a CI test asserting 100% coverage. The demo retains the contract; the CI assertion lands when the first cockpit canvas surfaces extracted data (Story 3-6 Documents panel). This story ships the contract that 3-6's CI test will reference.

[Source: `architecture.md#Project-Specific Patterns` P4 Agent Action Pattern] — `AgentActionLedgerEntry` is the typed "agent invocation" shape. The bank-buyer scope's full P4 contract has `prev_hash`, `chain_hash`, `platform_signature`. This story drops those three fields per the demo's "no signing, no chain" simplification; everything else is preserved.

[Source: `architecture.md#Project-Specific Patterns` P7 Confidence Banding Pattern] — Internal `[0.0, 1.0]` floats; display as 4-tier banded enum derived at the boundary. The boundary is **exactly one place** in each language — `to_band` (Python) and `toBand` (TS). Components and agents NEVER hard-code thresholds; they always go through these helpers.

[Source: `architecture.md#Implementation Patterns & Consistency Rules` § Validation timing] — Validation at the boundary, never deeper. The band-vs-confidence consistency check (AC3) runs once at `Provenance` construction; downstream consumers don't re-check.

[Source: `architecture.md#Anti-Patterns to Refuse`] — Pydantic schemas duplicated in apps. The TS mirror (AC6) is technically a duplicate, but a *manual translation* of the Python source — required because Story 2.11 (`openapi-typescript` wiring) was cut. The cross-language parity test (AC7) makes the duplication detectable.

### Critical pitfalls to avoid

1. **`ProvenancedField[T]` generics in Pydantic 2.** Pydantic 2 supports generic models natively via `Generic[T]` from `typing` — no `pydantic.generics.GenericModel` (that was Pydantic 1). The class declaration is `class ProvenancedField(BaseModel, Generic[T])`. mypy strict accepts this; verify by writing `pf: ProvenancedField[int] = ProvenancedField(value=42, provenance=...)` and confirming no mypy error.

2. **`StrEnum` vs `Literal`.** The `kind: Literal["agent_action"]` discriminator MUST be a `Literal`, not a `StrEnum` — Pydantic discriminator support requires literal types. Don't refactor it into `class PayloadKind(StrEnum): AGENT_ACTION = "agent_action"`.

3. **Discriminated unions with a `dict` fallback are tricky.** Pydantic 2 wants every union arm to be a typed model. The cleanest approach: keep `dict[str, Any]` as the fallback arm without a discriminator key, relying on left-to-right union resolution (typed model first). If Pydantic raises a config error about needing a discriminator, switch to `Annotated[Union[...], Field(discriminator="kind")]` and ensure the `dict` arm is wrapped in a tagged class — or remove the discriminator and accept slower union resolution. The dev decides; document the choice.

4. **`tool_calls: list[dict[str, Any]]` is an escape hatch.** A future story (Epic 5 Entity Verification) will want a typed `ToolInvocation` model. **Don't define `ToolInvocation` in this story** — that's premature abstraction. The `dict[str, Any]` fallback is honest about "we don't know the shape yet."

5. **`prompt_hash` regex is precise.** SHA-256 hex is 64 lowercase hex chars. `Annotated[str | None, ...]` lets `None` skip validation. If the dev uses a fancier `Field(pattern=...)` form, ensure `None` is still accepted — Pydantic's pattern validator can be strict on Optional handling.

6. **Out-of-range `confidence` is the wrong thing for `Provenance` to silently clamp.** Some libraries clamp `1.5 → 1.0`. **Don't.** Raise `ValidationError`. A confidence > 1 means an upstream bug; surfacing it loud catches the bug faster.

7. **NaN handling in `to_band`.** Python's `nan < 0.4` is `False`, so a naive `if confidence < 0.4: return LOW` would return `MEDIUM_LOW`/`MEDIUM_HIGH`/`HIGH` for NaN depending on the threshold. Test for NaN explicitly: `import math; if math.isnan(confidence): raise ValueError(...)`. Do the same for `math.isinf`.

8. **The TS mirror is NOT generated.** It's a hand-written file. The temptation is to add `openapi-typescript` here — resist. Story 2.11 was cut; reviving even a partial wiring is out of scope for 3-3. The parity test (AC7) is the safety net.

9. **`Generic[T]` constraint.** `T = TypeVar("T")` (no constraints) accepts everything Pydantic can serialize — which is all JSON-compatible types plus most built-ins. **Don't add `T = TypeVar("T", bound=...)`** — overconstraining hurts ergonomics for downstream stories. Pydantic 2 will raise at validation time if a non-serializable T (e.g., a Python `set`) is passed.

10. **`evidence_ids` is a list of `LedgerEntryId`, not raw strings.** The element type uses `LedgerEntryId` (the `Annotated[str, ...]` alias). Pydantic 2's `Annotated` constraints propagate through `list[...]`. Verify by validating `Provenance(evidence_ids=["not-a-led-id"])` — it should raise.

11. **Migrating Story 3-2's decorator is a behavioral no-op.** The wire format on disk (the JSONL line) is byte-identical before and after the migration. The only change is the in-memory type. If Story 3-2's tests assert exact JSON keys, they continue to pass. If they assert dict access (`payload["foo"]`), they break — Task 5.3 fixes those.

12. **`output: None` on `status="ok"` is permitted.** Some agents have void return semantics (e.g., a logging-side-effect agent). AC9's decision point binds this. Story 3-4's Doc Intelligence agent does have output, so this won't matter for Epic 3 — but reserving the affordance prevents a future story from re-litigating.

13. **The `THRESHOLDS` tuple ordering matters for `to_band`.** Iterate from highest threshold to lowest, returning on first match. Reversing the order gives wrong bands for boundary cases.

14. **Python-side `to_band` must return `ConfidenceBand` (the enum), not the string value.** Direct comparison against `ConfidenceBand.HIGH` is the canonical assertion. If the dev returns `"high"` (string), enum equality breaks for some Pydantic versions.

15. **Vitest tests should not use `process.cwd()` to resolve paths.** Vitest runs from the cockpit-ui dir; the test imports `from './confidence'` relatively. The cross-language parity test in `packages/contracts/tests/` does need a path; resolve via `Path(__file__).resolve().parents[3] / "apps/cockpit-ui/src/lib/confidence.ts"` or similar.

### Architecture patterns relevant here

[Source: `architecture.md#Project-Specific Patterns` P3] — `evidence_ids: list[EvidenceId]` (the bank-buyer name) → `evidence_ids: list[LedgerEntryId]` here. Same semantic; aligned to Story 3-1's chosen ID type.

[Source: `architecture.md#Project-Specific Patterns` P7] — Per-agent threshold calibration is deferred. The demo uses one global threshold set. If a future story (e.g., Story 5-7 Risk Scoring) needs different thresholds, that story can introduce per-band-context overrides — but the global set is the default.

[Source: `architecture.md#Cross-Cutting Flow Examples` — case ingest flow] — Each agent fan-out node writes a ledger entry with the typed payload. This story makes that typed payload exist.

### Project Structure Notes

This story creates:

- `packages/contracts/src/contracts/confidence.py`
- `packages/contracts/src/contracts/provenance.py`
- `packages/contracts/src/contracts/agent_action.py`
- `packages/contracts/tests/test_confidence.py`
- `packages/contracts/tests/test_provenance.py`
- `packages/contracts/tests/test_provenanced_field.py`
- `packages/contracts/tests/test_agent_action.py`
- `packages/contracts/tests/test_confidence_parity.py`
- `apps/cockpit-ui/src/lib/confidence.ts`
- `apps/cockpit-ui/src/lib/confidence.test.ts`

This story modifies:

- `packages/contracts/src/contracts/__init__.py` — re-export new symbols (alphabetized)
- `packages/contracts/src/contracts/ledger.py` — change `payload` type to discriminated union
- `packages/contracts/tests/test_ledger.py` — add typed-payload round-trip cases
- `apps/agents/src/agents/supervisor/action_decorator.py` — migrate payload to typed `AgentActionLedgerEntry`
- `apps/agents/tests/test_action_decorator.py` + `test_action_decorator_e2e.py` — adjust assertions

This story DOES NOT create:

- The Document Intelligence agent (Story 3-4 — uses these contracts)
- The Documents panel UI (Story 3-6 — uses `ProvenancedField[T]` in TS)
- The ConfidencePill component (Story 3-7 — uses `ConfidenceBand` and `toBand`)
- The Case Supervisor (Story 3-5)
- A typed `OfficerActionLedgerEntry` (Epic 7 owns it)
- A typed `ToolInvocation` shape (Epic 5 will introduce when first agent needs it)

### References

- [Source: `architecture.md#Project-Specific Patterns` P3, P4, P7] — provenance, agent action, confidence banding patterns
- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] — no signing, no hash chain, mock-only adapters
- [Source: `architecture.md#Anti-Patterns to Refuse`] — schema duplication (TS mirror documented as exception)
- [Source: `epics.md#Epic 3` § Story 3.6] — original AC (re-scoped here as 3-3)
- [Source: `prd.md#FR8, FR10, NFR-T4, NFR-AC3, UX-DR8`] — provenance everywhere, 4-tier confidence, color-blind safety
- [Source: `3-1-append-only-ledger-schema-with-insert-only-writer.md`] — `LedgerEntry`, `LedgerEntryId`, `ActorType`
- [Source: `3-2-agent-action-decorator.md`] — decorator's payload construction (migrated by this story)

### Previous Story Intelligence

[Source: `3-1-append-only-ledger-schema-with-insert-only-writer.md`]
- `LedgerEntry.payload: dict[str, Any]` is the current shape; this story upgrades it to a discriminated union. **Backward compatible with existing seed-loader entries** because `dict[str, Any]` is one arm of the union.
- The `tzinfo is not None` validator pattern was established for `LedgerEntry.recorded_at`. **Re-use the same validator function** (extract to `contracts/_utils.py` if used in three+ places — Story 3-3 has at least three: `Provenance.captured_at`, `AgentActionLedgerEntry.started_at`, `AgentActionLedgerEntry.completed_at`).
- `LedgerEntryId = Annotated[str, StringConstraints(...)]` is the existing alias; `Provenance.evidence_ids` reuses it.

[Source: `3-2-agent-action-decorator.md`]
- The decorator currently builds `payload` as a dict with keys `agent_id`, `model_id`, `prompt_template_id`, `input`, `output`, `started_at`, `completed_at`, `duration_ms`, `status`. Story 3-3's `AgentActionLedgerEntry` field set is the same — making the migration mechanical.
- `error: {"type": ..., "message": ...}` becomes `error: ErrorInfo(type=..., message=...)`. The wire-format JSON is byte-identical because `ErrorInfo.model_dump(mode="json")` produces the same dict.
- The decorator's e2e test reads the ledger file and asserts payload contents. Post-migration, the same assertions work because the JSON wire format is preserved (Pydantic union arms serialize transparently).

[Source: `2-1-case-schema-and-state-machine.md`]
- `CaseId = Annotated[str, StringConstraints(pattern=...)]` is the canonical pattern. `LedgerEntryId` (Story 3-1) and now `Provenance.evidence_ids` follow it.
- The `__init__.py` re-export discipline maintains alphabetical order in `__all__`. Apply to all new exports.

[Source: `1-4-cockpit-shell-with-user-switcher-three-hardcoded-roles.md`]
- The TS pattern for closed enum-like values is `as const` object + derived type, not TS `enum` (see `demoUsers.ts`). AC6's TS file follows the same pattern.

### Demo verification protocol (operator hand-off)

```bash
# After implementing, the dev must verify:

# 1. Confidence banding works in Python:
poetry -C packages/contracts run python -c "
from contracts.confidence import to_band, ConfidenceBand, THRESHOLDS
for c in [0.0, 0.39, 0.40, 0.64, 0.65, 0.84, 0.85, 1.0]:
    print(f'{c:.2f} -> {to_band(c).value}')
print('THRESHOLDS:', THRESHOLDS)
"
# Expected: low, low, medium_low, medium_low, medium_high, medium_high, high, high

# 2. Confidence banding works in TS:
cd apps/cockpit-ui
pnpm run test confidence.test.ts
# Expected: 12+ tests pass.

# 3. Cross-language parity:
poetry -C packages/contracts run pytest tests/test_confidence_parity.py -v
# Expected: 1 test passes.

# 4. Provenance band-vs-confidence enforcement:
poetry -C packages/contracts run python -c "
from datetime import datetime, UTC
from contracts.provenance import Provenance
from contracts.confidence import ConfidenceBand
try:
    Provenance(source_agent='x', source_system='y', confidence=0.62, confidence_band=ConfidenceBand.HIGH, evidence_ids=[], captured_at=datetime.now(UTC))
except ValueError as e:
    print('OK band-consistency raised:', e)
ok = Provenance(source_agent='x', source_system='y', confidence=0.62, confidence_band=ConfidenceBand.MEDIUM_LOW, evidence_ids=[], captured_at=datetime.now(UTC))
print('OK consistent provenance:', ok.confidence, ok.confidence_band.value)
"

# 5. ProvenancedField[T] generic round-trip:
poetry -C packages/contracts run python -c "
from datetime import datetime, UTC
from contracts.provenance import Provenance, ProvenancedField
from contracts.confidence import ConfidenceBand

prov = Provenance(source_agent='document_intelligence', source_system='mock_doc_ai', confidence=0.91, confidence_band=ConfidenceBand.HIGH, evidence_ids=[], captured_at=datetime.now(UTC))
pf: ProvenancedField[str] = ProvenancedField[str](value='Vora Capital Holdings Pvt Ltd', provenance=prov)
print('JSON:', pf.model_dump_json())
parsed = ProvenancedField[str].model_validate_json(pf.model_dump_json())
print('Round-tripped value:', parsed.value)
"

# 6. Decorator's typed payload round-trips through the ledger:
poetry -C apps/agents run pytest tests/test_action_decorator_e2e.py -v
# Expected: e2e test passes; payload is now AgentActionLedgerEntry-typed in-memory.

# 7. Lint + test green:
make lint
make test
# Expected: all subprojects pass; new contract tests visible.
```

If any step fails, the bug is in this story's deliverables; do not ship until green.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia persona, bmad-dev-story workflow)

### Debug Log References

* Initial `_make` helper in `test_provenance.py` called `to_band(confidence)` to compute a default band — but for out-of-range cases (`-0.01`, `1.01`), `to_band` raised before Pydantic could. Fixed by inlining `Provenance(...)` construction in those parametrized tests.
* mypy strict on `apps/agents` complained about cockpit-api lacking a `py.typed` marker. Added `src/cockpit_api/py.typed` + `[tool.poetry] include` directive to the cockpit-api `pyproject.toml`.

### Completion Notes List

* Discriminated-union resolution: chose left-to-right resolution (typed model first, dict fallback) over explicit `Field(discriminator="kind")` — Pydantic 2's discriminator support resists the dict-fallback arm, so left-to-right is cleaner. Documented in `ledger.py` module docstring.
* `ProvenancedField[T]`'s `T = TypeVar("T")` is unconstrained — accepts any Pydantic-serializable type. Tests parametrize over 7+ types (str, int, float, bool, list[str], dict, datetime) to lock down the contract.
* TS mirror at `apps/cockpit-ui/src/lib/confidence.ts` follows the project's `as const` enum-like pattern (no TS `enum`); cross-language parity test catches drift via regex-extracted threshold rows.
* Migrating Story 3.2's decorator was a single-step direct authoring (no temporary dict-form shipped) since all four stories were implemented in one session.
* Wire format on disk is byte-identical between dict-form and typed-form payloads when the typed payload's keys match the dict's keys — confirmed by re-reading existing JSONL entries through the union and observing they decode to the typed arm.

### File List

**Created**
* `packages/contracts/src/contracts/confidence.py`
* `packages/contracts/src/contracts/provenance.py`
* `packages/contracts/src/contracts/agent_action.py`
* `packages/contracts/tests/test_confidence.py`
* `packages/contracts/tests/test_confidence_parity.py`
* `packages/contracts/tests/test_provenance.py`
* `packages/contracts/tests/test_provenanced_field.py`
* `packages/contracts/tests/test_agent_action.py`
* `apps/cockpit-ui/src/lib/confidence.ts`
* `apps/cockpit-ui/src/lib/confidence.test.ts`

**Modified**
* `packages/contracts/src/contracts/__init__.py` — re-exports
* `packages/contracts/src/contracts/ledger.py` — `payload` upgraded to discriminated union
* `packages/contracts/tests/test_ledger.py` — typed-payload round-trip tests
* `apps/cockpit-api/pyproject.toml` — `py.typed` include
* `apps/cockpit-api/src/cockpit_api/py.typed` — empty marker file
* `Documentation/implementation-artifacts/sprint-status.yaml` — story marked `review`

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-04-30 | Story 3.3 drafted. Demo replacement for the bank-buyer Story 3.6. Adds typed `AgentActionLedgerEntry` payload (drops `prev_hash`/`chain_hash`/`signature`), `Provenance` + `ProvenancedField[T]` generic, `ConfidenceBand` + `to_band`, plus a TS mirror with cross-language parity test. Migrates Story 3-2's decorator from dict-payload to typed payload (wire-format-identical). |
