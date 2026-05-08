# Story 5.2: MCA lookup tool (mock)

Status: review

## Story

As the platform,
I want a typed `MCALookup` Protocol with a deterministic `MockMCALookup` impl that returns canonical MCA company-master records keyed by CIN, plus typed `MCANotFoundError` and `MCATemporaryError` exceptions for the agent's failure paths,
So that Story 5.1's Entity Verification agent has the typed authority source it needs without any vendor procurement, and Story 5.3's UBO Graph agent has typed director + shareholder data to seed the ownership graph (FR17 demo-scoped, P1 pluggable adapter pattern, Demo Scope Addendum mock-only).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 5.2 minus the network/rate-limit machinery. The original asked for a real MCA company-master HTTP wrapper with rate-limiting + typed transient errors; the demo retains the **typed Protocol + typed errors + typed Pydantic master record** but ships only the mock. No HTTP, no rate limit, no second impl.

| Bank-buyer scope (original 5.2) | Demo replacement in this story |
|---|---|
| Real HTTP MCA wrapper at `apps/agents/src/agents/tools/mca_lookup.py` | **Same path; mock impl only** at `apps/agents/src/agents/tools/mca_mock.py`. The Protocol + types live in `mca_lookup.py`. No network. |
| Rate-limit per MCA's published terms; 429 → `MCATemporaryError` | **No rate limit.** `MCATemporaryError` exists in the type hierarchy (so Entity Verification's failure path is exercisable in tests) but the mock raises it only when fed a magic CIN reserved for this purpose. |
| Pluggable adapter with conformance test pair | **Mock-only** per Demo Scope Addendum. `make lint-agents-p4` rule (Story 3.2) has no opinion on tool impls — only ledger writes. |
| ADK `@tool` decorator wrapping the function for Orchestrate registration | **No `@tool` decorator** (the demo's "tools" land as HTTP endpoints under `/v1/agents/*`, not Python `@tool` decorators — see Agent Runtime Update 2026-05-07). The MCA tool is consumed by the Entity Verification agent function directly via the Protocol. |

What survives: **typed `MCACompanyMaster` Pydantic model, `MCALookup` Protocol, two typed errors, deterministic fixture-driven mock keyed by CIN, fixtures cover all three demo cases plus the deliberate failure CINs.**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` § Stories simplified, `architecture.md#Demo Scope Addendum (2026-04-29)`, `architecture.md#Project-Specific Patterns` P1.

## Acceptance Criteria

1. **AC1 — Pydantic contracts at `packages/contracts/src/contracts/mca.py`.**

    ```python
    from typing import Literal
    from pydantic import BaseModel, Field

    MCAStatus = Literal["active", "struck_off", "dormant"]

    class MCADirector(BaseModel):
        model_config = {"frozen": True}
        din: str | None = Field(default=None, pattern=r"^\d{8}$")  # Director Identification Number, 8 digits
        name: str = Field(min_length=1)
        appointed_on: str | None = None      # ISO-8601 date
        designation: Literal["director", "managing_director", "additional_director", "nominee_director"] = "director"

    class MCAShareholder(BaseModel):
        model_config = {"frozen": True}
        name: str = Field(min_length=1)
        ownership_pct: float = Field(ge=0.0, le=100.0)
        country: str | None = None             # ISO 3166-1 alpha-2; None when MCA does not record
        is_corporate: bool = False             # individual vs corporate shareholder

    class MCACompanyMaster(BaseModel):
        model_config = {"frozen": True}
        cin: str = Field(min_length=21, max_length=21, pattern=r"^[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$")
        company_name: str = Field(min_length=1)
        status: MCAStatus
        registered_office: str = Field(min_length=1)
        incorporation_date: str = Field(min_length=10)   # ISO 8601 YYYY-MM-DD
        directors: list[MCADirector] = Field(default_factory=list)
        shareholders: list[MCAShareholder] = Field(default_factory=list)
    ```

    `MCAStatus` is a `Literal` (NOT a `StrEnum`) — same reasoning as Story 5.1 § AC1 (avoids spurious OpenAPI components).

    Re-export from `packages/contracts/src/contracts/__init__.py`. Names to add to `__all__`: `MCACompanyMaster`, `MCADirector`, `MCAShareholder`. **`MCAStatus` is also added to `__all__` in this story** (Story 5.1 may re-export the same name; both stories landing together: import `MCAStatus` from this contract module, not the `entity_verification` one — single source of truth).

    Re-exporting note: if Story 5.1 has already re-exported `MCAStatus` from `entity_verification.py`, **delete that re-export** and have `entity_verification.py` import the type from `mca.py`. Don't duplicate.

2. **AC2 — `MCALookup` Protocol + typed errors at `apps/agents/src/agents/tools/mca_lookup.py`.**

    ```python
    """MCA lookup tool — Story 5.2.

    Mock-only in the demo (see architecture.md § Demo Scope Addendum).
    Entity Verification (Story 5.1) consumes this via the Protocol.
    """
    from __future__ import annotations
    from typing import Protocol, runtime_checkable

    from contracts.mca import MCACompanyMaster

    class MCALookupError(RuntimeError):
        """Base for all MCA-tool errors."""

    class MCANotFoundError(MCALookupError):
        """Raised when a CIN does not resolve to an MCA master."""
        def __init__(self, cin: str) -> None:
            self.cin = cin
            super().__init__(f"MCA: no company master for CIN {cin!r}")

    class MCATemporaryError(MCALookupError):
        """Raised when MCA is unavailable (network / rate-limit / 5xx).

        In the demo this is raised only by the mock when fed a magic CIN
        reserved for failure-path tests (see AC4).
        """

    @runtime_checkable
    class MCALookup(Protocol):
        async def lookup(self, *, cin: str) -> MCACompanyMaster: ...
    ```

    The module is **import-clean** under `mypy strict` and `ruff` — no `# type: ignore`, no `Any`. The Protocol method is `async` because the bank-buyer scope's real impl is async; the mock is also async to keep the call sites symmetric (no `if asyncio.iscoroutine(...)` branching downstream).

3. **AC3 — `MockMCALookup` impl at `apps/agents/src/agents/tools/mca_mock.py`.**

    ```python
    """Deterministic mock MCA lookup. Demo default."""
    from __future__ import annotations
    from contracts.mca import MCACompanyMaster, MCADirector, MCAShareholder
    from agents.tools.mca_lookup import MCALookup, MCANotFoundError, MCATemporaryError

    _FIXTURES: dict[str, MCACompanyMaster] = { ... }   # see AC4
    _MAGIC_CIN_TEMPORARY_ERROR = "U99999XX9999XXX999999"   # see AC4

    class MockMCALookup(MCALookup):
        async def lookup(self, *, cin: str) -> MCACompanyMaster:
            if cin == _MAGIC_CIN_TEMPORARY_ERROR:
                raise MCATemporaryError("MCA mock: deliberate transient failure")
            try:
                return _FIXTURES[cin]
            except KeyError as exc:
                raise MCANotFoundError(cin) from exc
    ```

    Module-level `model_id: str = "mock"` for completeness — though MCA is not LLM-driven and Story 5.1's Entity Verification ledger entry's `model_id="deterministic"`, the property exists on the class for symmetry with `FixtureDocAILLM` from Story 3.4.

4. **AC4 — `_FIXTURES` covers every demo CIN (and the failure-path CINs).**

    The mock must answer for the CINs present in the three demo case fixtures (`packages/contracts/src/contracts/cases.py`). Currently:

    | Case | `customer_metadata.extra.registration_number` |
    |---|---|
    | Shree Venkat Trading | `U51900MH2018PTC312456` |
    | Vora Capital Holdings Pvt Ltd | `U67120MH2024PTC444789` |
    | Ananya Iyer | (none — individual) |

    Plus deliberate failure CINs:

    | Magic CIN | Behaviour |
    |---|---|
    | `U99999XX9999XXX999999` | raises `MCATemporaryError` (failure path test) |
    | `U99999YY9999YYY999999` | absent from `_FIXTURES`, falls through to `MCANotFoundError` (failure path test) |

    Canonical fixture content (deterministic; the demo's narrative arc):

    * **Shree Venkat Trading** (clean approval narrative; MCA matches case-side; no UBO complexity):
      ```python
      MCACompanyMaster(
          cin="U51900MH2018PTC312456",
          company_name="Shree Venkat Trading Pvt Ltd",
          status="active",
          registered_office="Plot 14, MIDC Industrial Area, Pune, Maharashtra 411019",
          incorporation_date="2018-03-15",
          directors=[
              MCADirector(din="08123456", name="Venkat Reddy", appointed_on="2018-03-15", designation="director"),
              MCADirector(din="08123457", name="Lakshmi Reddy", appointed_on="2018-03-15", designation="director"),
          ],
          shareholders=[
              MCAShareholder(name="Venkat Reddy", ownership_pct=70.0, country="IN", is_corporate=False),
              MCAShareholder(name="Lakshmi Reddy", ownership_pct=30.0, country="IN", is_corporate=False),
          ],
      )
      ```

    * **Vora Capital Holdings Pvt Ltd** (hairy UBO narrative; MCA matches case-side fields but the shareholder pattern includes a foreign LLC + corporate holder that the UBO Graph agent (Story 5.3) flags as `nominee_suspected`):
      ```python
      MCACompanyMaster(
          cin="U67120MH2024PTC444789",
          company_name="Vora Capital Holdings Pvt Ltd",
          status="active",
          registered_office="Suite 402, Sea Breeze Heights, Bandra West, Mumbai 400050",
          incorporation_date="2024-08-22",
          directors=[
              MCADirector(din="09876543", name="Devansh Vora", appointed_on="2024-08-22", designation="managing_director"),
              MCADirector(din="09876544", name="Rohan Mehta", appointed_on="2024-08-22", designation="director"),
              MCADirector(din="09876545", name="A K Filing Services", appointed_on="2024-08-22", designation="nominee_director"),
          ],
          shareholders=[
              # Direct individual: 5%
              MCAShareholder(name="Devansh Vora", ownership_pct=5.0, country="IN", is_corporate=False),
              # Foreign LLC majority holder — nominee suspect signal for Story 5.3
              MCAShareholder(name="Coastal Equity Partners Pte Ltd", ownership_pct=70.0, country="SG", is_corporate=True),
              # Trust services BVI — second nominee suspect signal
              MCAShareholder(name="Anchor Trust Services (BVI)", ownership_pct=25.0, country="VG", is_corporate=True),
          ],
      )
      ```

    Why the Vora shareholder pattern matters: Story 5.3's heuristics flag corporate shareholders in **non-IN jurisdictions** + nominee-director designations as `nominee_suspected`. The fixture is deliberately shaped so Vora has **two** nominee-suspected edges. Don't tweak the percentages without re-running Story 5.3's tests.

    Both fixtures land as module-level `MCACompanyMaster` instances (frozen Pydantic). The dict literal must be **fully constructed at import time** — no lazy lambdas; the `_FIXTURES` table is the source of truth.

5. **AC5 — Default-resolver helper.**

    ```python
    # apps/agents/src/agents/tools/mca_lookup.py
    import os
    from agents.tools.mca_mock import MockMCALookup

    def get_default_mca_lookup() -> MCALookup:
        provider = os.environ.get("MCA_PROVIDER", "mock")
        if provider == "mock":
            return MockMCALookup()
        raise ValueError(f"Unknown MCA_PROVIDER {provider!r}; only 'mock' is supported in the demo")
    ```

    Story 5.1 calls this resolver. **Don't pre-empt Story 5.6 (Risk Scoring) or anywhere else** — they don't call MCA directly; they read `EntityVerificationResult` from `IntakeRepo`.

6. **AC6 — Tests in `apps/agents/tests/test_mca_lookup.py`.** Cover:

    * **Vora CIN returns the canonical fixture** — assert all top-level fields, all directors, all shareholders.
    * **Shree CIN returns the canonical fixture.**
    * **Unknown CIN raises `MCANotFoundError`** — assert the error's `cin` attribute matches the input.
    * **Magic temporary CIN raises `MCATemporaryError`** — assert the type and a string-equal message.
    * **Protocol satisfaction** — `isinstance(MockMCALookup(), MCALookup)` is True (because Protocol is `runtime_checkable`).
    * **`get_default_mca_lookup()` returns a `MockMCALookup` instance** when `MCA_PROVIDER` is unset.
    * **`get_default_mca_lookup()` returns a `MockMCALookup` instance** when `MCA_PROVIDER="mock"`.
    * **`get_default_mca_lookup()` raises `ValueError`** on unknown provider; assert the message names the provider.
    * **Module-level fixture immutability** — assert `_FIXTURES["U67120MH2024PTC444789"].directors[0].name == "Devansh Vora"`; mutate via `model_copy(update={...})` and assert the original is unchanged (frozen Pydantic invariant).

7. **AC7 — Contract tests in `packages/contracts/tests/test_mca.py`.** Cover:

    * Round-trip `MCACompanyMaster.model_validate(master.model_dump(mode="json"))` matches the original.
    * Each constraint fires: invalid CIN regex → `ValidationError`; `MCAStatus` value `"active "` (trailing space) → `ValidationError`; `MCAShareholder.ownership_pct=101.0` → `ValidationError`; `MCAShareholder.country="india"` (3-letter) — **note: country is a free-form `str` in this contract**, so no validation. If you want stricter ISO-3166-1, add a `Field(pattern=r"^[A-Z]{2}$")`. **Do not** add the pattern in this story — the bank-buyer scope might want flexibility for shell-jurisdiction codes; revisit if needed in Story 5.3.

8. **AC8 — `make demo-reset && make seed && make test` clean.** Net new test count: ≥ 9 in `test_mca_lookup.py`; ≥ 4 in `test_mca.py`. No ledger entries are written by this story (no agent action, no supervisor call); a `make seed` run produces the same 4 baseline ledger lines as before.

9. **AC9 — `mypy strict` clean across `apps/agents` and `packages/contracts`.** No `Any`, no `# type: ignore`, no `cast` calls. The `runtime_checkable` Protocol does **not** confuse mypy strict — it does require the `runtime_checkable` decorator at the Protocol definition.

10. **AC10 — No supervisor / cockpit-api wiring in this story.** This story ships the tool as importable Python only; Story 5.1 wires it into the Entity Verification agent + its HTTP endpoint. No new ADK registry entry (this is a tool the agent calls internally, not an HTTP-callable Orchestrate tool). No new env vars in `.env.example` (the `MCA_PROVIDER=mock` default is implicit).

## Tasks / Subtasks

- [x] **Task 1 — Author Pydantic contracts** (AC: #1)
  - [x] Subtask 1.1 — `packages/contracts/src/contracts/mca.py` with `MCAStatus`, `MCADirector`, `MCAShareholder`, `MCACompanyMaster`.
  - [x] Subtask 1.2 — Re-export from `packages/contracts/src/contracts/__init__.py` (alphabetical).
  - [x] Subtask 1.3 — Coordinate with Story 5.1: if 5.1's `entity_verification.py` re-exports `MCAStatus`, change to `from contracts.mca import MCAStatus`. *(5.1 not yet implemented; Story 5.1 will import from `contracts.mca` per AC1 here.)*

- [x] **Task 2 — Author the Protocol + typed errors** (AC: #2, #5)
  - [x] Subtask 2.1 — `apps/agents/src/agents/tools/__init__.py` (empty marker created).
  - [x] Subtask 2.2 — `apps/agents/src/agents/tools/mca_lookup.py` with `MCALookupError`, `MCANotFoundError`, `MCATemporaryError`, `MCALookup` Protocol, `get_default_mca_lookup()`.

- [x] **Task 3 — Author the mock impl** (AC: #3, #4)
  - [x] Subtask 3.1 — `apps/agents/src/agents/tools/mca_mock.py` with `_FIXTURES`, `_MAGIC_CIN_TEMPORARY_ERROR`, `MockMCALookup`.
  - [x] Subtask 3.2 — Both demo fixtures (Shree, Vora) constructed at module import time.
  - [x] Subtask 3.3 — Vora's shareholder pattern: 70% SG corporate + 25% VG corporate + nominee_director designation (load-bearing for Story 5.3).

- [x] **Task 4 — Tests** (AC: #6, #7, #8, #9)
  - [x] Subtask 4.1 — `apps/agents/tests/test_mca_lookup.py` covers all 9 cases from AC6.
  - [x] Subtask 4.2 — `packages/contracts/tests/test_mca.py` covers AC7 (8 tests).
  - [x] Subtask 4.3 — Ruff + mypy strict clean across `apps/agents` and `packages/contracts`.
  - [x] Subtask 4.4 — Python `make test` green (62 agents, 156 contracts). TS test failures in `apps/cockpit-ui/src/hooks/useCases.test.tsx` are pre-existing in the uncommitted working tree (unrelated to this story — no UI files modified).

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] Vendor adapters → mock-only. **Cement: no HTTP, no rate limit, no second impl.** The Protocol is the door for a future bank-buyer revival.
* [Source: `architecture.md#Project-Specific Patterns` P1 Pluggable Adapter Pattern] In bank-buyer scope, every adapter ships with a second reference impl + a conformance suite. Demo simplification (architecture.md addendum) explicitly waives this. The Protocol exists; the second impl does not.
* [Source: `architecture.md#Validation timing`] Pydantic at the boundary. The mock returns a `MCACompanyMaster` (Pydantic-validated by construction); Story 5.1's agent function trusts that and re-uses field values without re-validation.
* [Source: `architecture.md#Naming Patterns`] Wire format is snake_case. `MCAStatus` values are `"active"`, `"struck_off"`, `"dormant"` — all snake_case. `MCADirector.designation` follows the same rule (`managing_director`, `nominee_director`, etc.).
* [Source: `architecture.md#Anti-Patterns to Refuse`] No schema duplication. `MCAStatus` lives in `mca.py` only; `entity_verification.py` (Story 5.1) imports it.

### Critical pitfalls

1. **`MCAStatus` ownership.** Both this story and Story 5.1 reference `MCAStatus`. **This story is the owner**; Story 5.1 imports. If they merge in either order, the merging dev must verify single-source-of-truth.

2. **`MCADirector.din` is `Optional[str]`.** Demo fixtures populate every DIN, but real MCA records sometimes omit DINs for retired directors; keep the field nullable so the bank-buyer revival doesn't churn the contract. Tests should cover `din=None` round-trip.

3. **Vora's shareholder-pattern ratios are load-bearing.** Story 5.3's nominee-detection heuristic looks for: (a) corporate shareholders in non-IN jurisdictions, (b) ownership > 50% by such holders, (c) nominee-director-designation appointments. **Do not** "round" the percentages or change country codes (`SG` vs `VG`) without coordinating with Story 5.3's tests.

4. **`runtime_checkable` is required for `isinstance(impl, Protocol)`.** Without the decorator, the AC6 isinstance check raises `TypeError`. mypy is fine without it; the runtime check requires it.

5. **The Protocol's method is `async`.** Even though the mock is purely in-memory, the demo's call sites use `await`. If you make the mock sync, every Story 5.1 + 5.3 call site needs `if isinstance(...)` branching — don't do that.

6. **The CIN regex** is `^[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$` — same as the document_intelligence taxonomy in Story 3.4. **Don't relax it.** The mock's failure-path "magic" CINs (`U99999XX9999XXX999999`, `U99999YY9999YYY999999`) deliberately match the regex, so they pass `EntityVerificationInput` validation but don't appear in `_FIXTURES`. This is the only way to test Story 5.1's failure paths through the FastAPI boundary.

7. **`_FIXTURES` is `dict[str, MCACompanyMaster]`, not `dict[CIN, MCACompanyMaster]`.** There's no `CIN` typed alias — the regex check happens at construction time on `MCACompanyMaster.cin`. Keying on raw `str` keeps the dict literal compact.

8. **No env vars or config.** `MCA_PROVIDER` defaults to `"mock"` and is the only supported value. Do **not** add it to `.env.example` — that file is for runtime env vars an operator configures, not internal-only knobs. Document the env var in `mca_lookup.py`'s module docstring.

### Story dependencies

* **No prereqs** — this story has only `packages/contracts` (already shipped) as a dependency.
* **Read by:** Story 5.1 (Entity Verification agent), Story 5.3 (UBO Graph agent — uses `MCADirector` + `MCAShareholder` to seed the graph). If 5.3 ships before 5.1, this story still doesn't change.

### Project Structure Notes

This story creates:
- `packages/contracts/src/contracts/mca.py`
- `packages/contracts/tests/test_mca.py`
- `apps/agents/src/agents/tools/__init__.py` (if absent — verify before authoring)
- `apps/agents/src/agents/tools/mca_lookup.py`
- `apps/agents/src/agents/tools/mca_mock.py`
- `apps/agents/tests/test_mca_lookup.py`

This story modifies:
- `packages/contracts/src/contracts/__init__.py` — re-exports

This story DOES NOT create:
- Any FastAPI router (no HTTP boundary; tools are internal Python)
- Any ADK registry entry (no Orchestrate-callable tool here)
- A second-impl conformance suite (waived per Demo Scope Addendum)
- A GST-equivalent (cut from demo)

### References

- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] mock-only adapters
- [Source: `architecture.md#Project-Specific Patterns` P1] Pluggable adapter pattern (waived but Protocol shape preserved)
- [Source: `architecture.md#Naming Patterns`] snake_case enums
- [Source: `epics.md#Epic 5` § Story 5.2] original AC (re-scoped here)
- [Source: `prd.md#FR17`] cross-reference authority sources (MCA-only in demo)
- [Source: `2-4-fixture-case-loader-with-three-seeded-cases.md`] Vora's pinned CIN + UBO chain hint; Shree's CIN
- [Source: `5-1-entity-verification-agent.md`] consumer of this tool

### Demo verification protocol

```bash
# 1. Lint + test (no make seed needed; this story has no runtime side effects):
make lint && make test
# Expected: green; new tests visible in apps/agents and packages/contracts coverage.

# 2. Direct mock call:
poetry -C apps/agents run python -c "
import asyncio
from agents.tools.mca_mock import MockMCALookup

async def main():
    m = MockMCALookup()
    vora = await m.lookup(cin='U67120MH2024PTC444789')
    print('vora status=', vora.status, 'directors=', len(vora.directors), 'shareholders=', len(vora.shareholders))
    print('foreign-LLC holder:', [s.name for s in vora.shareholders if s.country != 'IN'])
asyncio.run(main())
"
# Expected: vora status=active directors=3 shareholders=3
#           foreign-LLC holder: ['Coastal Equity Partners Pte Ltd', 'Anchor Trust Services (BVI)']

# 3. Failure paths:
poetry -C apps/agents run python -c "
import asyncio
from agents.tools.mca_mock import MockMCALookup
from agents.tools.mca_lookup import MCANotFoundError, MCATemporaryError

async def main():
    m = MockMCALookup()
    try:
        await m.lookup(cin='U99999YY9999YYY999999')
    except MCANotFoundError as e:
        print('not-found cin:', e.cin)
    try:
        await m.lookup(cin='U99999XX9999XXX999999')
    except MCATemporaryError as e:
        print('temporary:', e)
asyncio.run(main())
"
# Expected: not-found cin: U99999YY9999YYY999999
#           temporary: MCA mock: deliberate transient failure
```

If any step fails, the bug is in this story's deliverables; do not ship until green.

## Dev Agent Record

### Agent Model Used

(claude-opus-4-7 + Amelia persona, bmad-dev-story workflow)

### Debug Log References

* Ruff initially flagged unsorted imports in `tests/test_mca_lookup.py`; fixed via `ruff check --fix`.
* `MCAStatus` is owned by `packages/contracts/src/contracts/mca.py`; Story 5.1 (when implemented) must `from contracts.mca import MCAStatus`, not redefine.
* AC4 magic CIN for `MCATemporaryError` is module-level `_MAGIC_CIN_TEMPORARY_ERROR`; the not-found magic CIN (`U99999YY9999YYY999999`) is implicit (just absent from `_FIXTURES`).
* `MCALookup` Protocol is `runtime_checkable` for `isinstance(MockMCALookup(), MCALookup)` test.
* `get_default_mca_lookup()` does a lazy import of `MockMCALookup` inside the function body to avoid circular import (the mock imports `MCALookup` from this module).

### Completion Notes List

* All 10 ACs satisfied. Net new tests: 9 in `test_mca_lookup.py`, 8 in `test_mca.py` (≥ AC8 minimums).
* Mypy strict clean across both packages; no `Any`, no `# type: ignore`, no `cast`.
* No supervisor / cockpit-api wiring per AC10; this story ships importable Python only.
* No ledger entries written by this story (no agent action). `make seed` baseline unchanged.
* `make demo-reset` ran cleanly; AC verification protocol output matches expected.

### File List

**Created:**
- `packages/contracts/src/contracts/mca.py`
- `packages/contracts/tests/test_mca.py`
- `apps/agents/src/agents/tools/__init__.py`
- `apps/agents/src/agents/tools/mca_lookup.py`
- `apps/agents/src/agents/tools/mca_mock.py`
- `apps/agents/tests/test_mca_lookup.py`

**Modified:**
- `packages/contracts/src/contracts/__init__.py` — re-export `MCACompanyMaster`, `MCADirector`, `MCAShareholder`, `MCAStatus`.

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-08 | Story 5.2 drafted. Demo replacement for the bank-buyer Story 5.2: typed Pydantic master record + Protocol + typed errors + deterministic mock keyed by CIN. GST tool (original 5.3) cut entirely. |
| 2026-05-08 | Story 5.2 implemented. Contracts (`mca.py`), Protocol + typed errors (`mca_lookup.py`), mock impl with Shree + Vora fixtures (`mca_mock.py`), 9 tool tests + 8 contract tests, ruff + mypy strict clean. |
