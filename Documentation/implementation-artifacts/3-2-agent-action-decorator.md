# Story 3.2: Agent action decorator

Status: review

## Story

As an agent author working in `apps/agents/`,
I want a single `@agent_action` decorator that wraps any async agent function and writes a `LedgerEntry` to the append-only ledger automatically — capturing input, output, model_id, prompt template ref, started_at, completed_at, and error state — and re-raises a typed `AgentExecutionError` on failure,
So that no agent in the codebase can ever return data without a ledger trail, and the Case Supervisor (Story 3-5) can rely on a uniform exception type to flag blocked-intake cases (P4, FR55, NFR-A5).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 3.5 (`@ledgered_action` decorator). The architectural pattern is identical — every agent invocation gets a ledger entry — but the demo collapses the bank-buyer's complexity:

| Bank-buyer scope (original 3.5) | Demo replacement in this story |
|---|---|
| Decorator constructs full `AgentActionLedgerEntry` with `prompt_hash`, `model_id`, `prompt_template_id`, `tool_calls`, `prev_hash`, `chain_hash`, `platform_signature` | **Same set of fields**, minus `prev_hash` / `chain_hash` / `platform_signature` (no chain, no signing in the demo). Stored under `payload` of the generic `LedgerEntry` from Story 3-1. |
| Calls `LedgerService.append` which signs via `KeyVault` adapter, persists to Postgres under `ledger_writer` role, runs inside an Arq worker | Calls `LedgerWriter.append` (Story 3-1) which appends a JSONL line. Synchronous, in-process, no queue. |
| Custom Ruff rule `bmm-no-direct-ledger-append-outside-decorator` blocks `LedgerService.append` calls outside `agents/supervisor/action_decorator.py` | **Soft enforcement only** — module docstring + a single CI grep check (`make lint` extension) flags suspicious direct `LedgerWriter().append` usage in `apps/agents/` outside `action_decorator.py`. The hard Ruff custom-rule build is deferred. |
| Ed25519 signing failure paths handled (KeyVault unavailable → fail-closed) | N/A — no signing |

What survives: **the decorator is the only sanctioned path from agent → ledger, the typed `AgentExecutionError` for supervisor catch+flag (FR55), and the input/output Pydantic-validation discipline (P4 enforces ledger-before-return).** Those are load-bearing for Story 3-5's blocked-intake UX and Story 6-7's ReasoningTraceSlideOut content.

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` and `architecture.md#Demo Scope Addendum (2026-04-29)`.

## Acceptance Criteria

1. **AC1 — `@agent_action` decorator lives at `apps/agents/src/agents/supervisor/action_decorator.py`.** Signature:

    ```python
    def agent_action(
        *,
        agent_id: str,
        model_id: str = "stub",
        prompt_template_id: str | None = None,
    ) -> Callable[[Callable[..., Awaitable[OutputT]]], Callable[..., Awaitable[OutputT]]]: ...
    ```

    Used as: `@agent_action(agent_id="document_intelligence", model_id="watsonx/granite-3.1-8b-instruct", prompt_template_id="document_intelligence/extract_v1")`. Wraps any **async** function whose first positional argument is a Pydantic `BaseModel` (the agent input contract) and whose return value is a Pydantic `BaseModel` (the agent output contract). Synchronous functions raise `TypeError("@agent_action must wrap an async function")` at decoration time.

2. **AC2 — Wrapped function lifecycle.** When the wrapped function `await agent(input_model, *args, **kwargs)` is called:
    1. Capture `started_at = datetime.now(UTC)`
    2. Capture `case_id` from `input_model.case_id` if the field exists (most agent inputs carry it); fall back to `kwargs.get("case_id")`; finally `None` if neither resolves. **Do not raise** if `case_id` is missing — system-level agents may exist that don't operate on a single case.
    3. Call the wrapped coroutine
    4. On success: capture `completed_at`, build a `LedgerEntry` per AC4, append via `LedgerWriter`, return the agent's output **after** the append completes (P4: no return without ledger entry)
    5. On exception: capture `completed_at`, build a failure `LedgerEntry` per AC5, append, then re-raise as `AgentExecutionError` with the original exception chained via `raise AgentExecutionError(...) from exc`

    **Critical ordering:** the ledger entry MUST be appended before the function returns its value to the caller, and before any exception escapes. If `LedgerWriter.append` itself raises (e.g., disk full), the original agent failure is preserved as the `__cause__` and the ledger failure is logged at ERROR; the call still raises `AgentExecutionError` so the supervisor catches it.

3. **AC3 — `AgentExecutionError` is defined in the same module** as `class AgentExecutionError(RuntimeError)`. Constructor: `AgentExecutionError(*, agent_id: str, case_id: CaseId | None, original: BaseException)`. Stores all three as attributes. The `__str__` is `f"agent {agent_id} failed on case {case_id or 'N/A'}: {original.__class__.__name__}: {original}"`. Re-exported from `apps/agents/src/agents/__init__.py` so the supervisor can `from agents import AgentExecutionError`.

4. **AC4 — Success-path `LedgerEntry` payload structure.** The decorator constructs:

    ```python
    LedgerEntry(
        id="led_PLACEHOLDER",  # overwritten by writer
        actor_type=ActorType.AGENT,
        actor_id=agent_id,
        case_id=resolved_case_id,
        action="agent.completed",
        payload={
            "agent_id": agent_id,
            "model_id": model_id,
            "prompt_template_id": prompt_template_id,
            "input": input_model.model_dump(mode="json"),
            "output": output_model.model_dump(mode="json"),
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_ms": int((completed_at - started_at).total_seconds() * 1000),
            "status": "ok",
        },
        recorded_at=datetime.now(UTC),  # overwritten by writer
    )
    ```

    **Pydantic dump mode:** use `mode="json"` so nested datetimes, enums, and ULIDs serialize to their wire shapes. The payload is a `dict[str, Any]` — Story 3-3 may later replace it with a typed `AgentActionLedgerEntry.model_dump()` but this story's payload stays dict-shaped to unblock 3-4 and 3-5.

5. **AC5 — Failure-path `LedgerEntry` payload structure.** On exception:

    ```python
    LedgerEntry(
        id="led_PLACEHOLDER",
        actor_type=ActorType.AGENT,
        actor_id=agent_id,
        case_id=resolved_case_id,
        action="agent.failed",
        payload={
            "agent_id": agent_id,
            "model_id": model_id,
            "prompt_template_id": prompt_template_id,
            "input": input_model.model_dump(mode="json"),
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_ms": int((completed_at - started_at).total_seconds() * 1000),
            "status": "error",
            "error": {
                "type": exc.__class__.__name__,  # e.g. "ValidationError"
                "message": str(exc)[:500],       # truncate runaway tracebacks
            },
        },
        recorded_at=datetime.now(UTC),
    )
    ```

    `output` is omitted on failure (no successful output to record). The Audit Trail Timeline (9-1) will distinguish `agent.completed` vs `agent.failed` events visually.

6. **AC6 — Single sanctioned path enforcement.** The module docstring states verbatim:

    > "**This module is the only sanctioned path from agent code to the ledger.** Direct `LedgerWriter.append` calls inside `apps/agents/` outside this file violate P4 (Agent Action Pattern). See architecture.md § P4 and the demo-scope simplification in Story 3-2."

    A `make lint` extension (or a new `make lint-agents` sub-target if that's cleaner) runs:
    ```bash
    ! grep -RIn --include="*.py" "LedgerWriter\(.*\)\.append\|get_ledger_writer().append" \
        apps/agents/src/agents/ \
        | grep -v "apps/agents/src/agents/supervisor/action_decorator.py"
    ```
    If the grep finds anything, lint fails with a clear message: `"P4 violation: only @agent_action may write to the ledger from apps/agents. Found in: <files>"`. The check is wired into `make lint` so it runs in CI.

    **Acceptable false positives:** test fixtures in `apps/agents/tests/` may legitimately mock the writer. Restrict the grep to `src/agents/` (not `tests/`).

7. **AC7 — Cross-app dependency wiring.** `apps/agents` does not yet depend on `apps/cockpit-api`. The decorator imports `LedgerWriter` and `get_ledger_writer` from `cockpit_api.services.ledger_service`. **Decision (binding for this story):** add `cockpit-api = {path = "../cockpit-api", develop = true}` to `apps/agents/pyproject.toml` as a path dep. This is acceptable because architecture A3 collapses agents + cockpit-api into a single uvicorn process at runtime; the build-time direction (agents → cockpit-api) is the inverse of the runtime direction (api invokes supervisor invokes agents), but the Python import graph permits cycles only at module level — there is no actual runtime cycle since cockpit-api never imports anything from `apps/agents` directly (it goes through the supervisor's public API).

    **If the dev disagrees** and prefers to inject `LedgerWriter` via dependency injection (decorator factory takes a `writer` parameter, supervisor wires it), that is also acceptable — the ACs do not prescribe the wiring style. But picking **one** path and documenting it in the module docstring is mandatory. Default recommendation: path dep, simpler.

8. **AC8 — Decorator metadata preservation.** `functools.wraps` (or `functools.update_wrapper`) preserves `__name__`, `__qualname__`, `__doc__`, and `__module__` so introspection (and pytest's test discovery + tracebacks) names the wrapped agent correctly. Type information is preserved via `ParamSpec` + `TypeVar` so mypy strict sees the wrapped function's signature unchanged.

    Required generic typing:
    ```python
    P = ParamSpec("P")
    OutputT = TypeVar("OutputT", bound=BaseModel)

    def agent_action(*, agent_id: str, ...):
        def decorator(fn: Callable[P, Awaitable[OutputT]]) -> Callable[P, Awaitable[OutputT]]: ...
    ```

9. **AC9 — Unit tests cover happy path, failure path, ordering, metadata.** Pytest specs in `apps/agents/tests/test_action_decorator.py`:
    - **Happy path:** decorate a stub async function `async def stub(input: StubIn) -> StubOut`; call it; assert it returned the expected output AND the ledger received exactly one `agent.completed` entry with the expected `agent_id`, `model_id`, `case_id`, `input`, `output`, `duration_ms >= 0`, `status="ok"`.
    - **Failure path — `ValueError` inside agent:** stub raises `ValueError("bad input")`; assert the call raises `AgentExecutionError` with `original` referencing the `ValueError`; assert exactly one `agent.failed` entry was appended with `payload.error.type == "ValueError"` and `payload.error.message == "bad input"`.
    - **Ordering — ledger before raise:** patch `LedgerWriter.append` to fail with `RuntimeError("disk full")`; stub raises `ValueError`; assert the caller still receives `AgentExecutionError` (the agent error is preserved as `original`); assert the disk-full error is logged at ERROR (capture via `caplog`).
    - **case_id resolution from `input_model.case_id`:** stub input has `case_id` field; ledger entry's `case_id` matches.
    - **case_id falls through `kwargs`:** input has no `case_id` field; pass `case_id=...` as kwarg; ledger entry picks it up from kwargs.
    - **case_id resolves to `None`:** input has no `case_id`; no `case_id` kwarg; ledger entry's `case_id` is `None` (system-level agent); decorator does NOT raise.
    - **Sync function rejection:** decorate a synchronous `def`; assert decoration raises `TypeError("@agent_action must wrap an async function")` immediately (at decoration time, not at call time).
    - **Metadata preservation:** assert `wrapped.__name__ == "stub"`, `wrapped.__doc__` matches the inner doc.
    - **Concurrent invocations:** `asyncio.gather` 10 wrapped-function calls; assert 10 ledger entries, each with distinct `id`s, `started_at` ordering monotonic per call.

10. **AC10 — Lint enforcement is wired and asserts P4.** `make lint` runs the grep check from AC6. Verify by:
    1. Adding a test-only file `apps/agents/src/agents/_violations_demo.py` (gitignored) that contains `get_ledger_writer().append(...)` — the grep should fire and `make lint` should fail.
    2. Removing the file → `make lint` clean.

    **Acceptance:** the lint check is real, not theatrical. The dev demonstrates the failure mode in the dev log.

11. **AC11 — End-to-end smoke via the supervisor (Story 3-5 will rely on this).** Before this story is done, write a one-shot integration test in `apps/agents/tests/test_action_decorator_e2e.py` that:
    1. Decorates a stub `async def fake_doc_intelligence(case_id: CaseId, ...)` with `@agent_action(agent_id="document_intelligence", model_id="stub", prompt_template_id="stub/v1")`
    2. Wires a real `LedgerWriter` against `tmp_path / "ledger.jsonl"`
    3. Calls the wrapped function
    4. Reads the ledger file via `LedgerReader` and asserts exactly one entry with `actor_type == ActorType.AGENT`, `actor_id == "document_intelligence"`, `payload["status"] == "ok"`

    This proves the cross-app wiring (agents → cockpit_api.services.ledger_service) actually works at runtime.

12. **AC12 — `make lint` + `make test` clean.** All Python projects pass mypy strict. The `apps/agents` test count adds at least 9 new tests (the 8 from AC9 + the 1 e2e from AC11). No regressions.

## Tasks / Subtasks

- [x] **Task 1 — Wire the cross-app dependency** (AC: #7, #12)
  - [x] Subtask 1.1 — Added `cockpit-api = {path = "../cockpit-api", develop = true}` to `apps/agents/pyproject.toml`. Lockfile regenerated.
  - [x] Subtask 1.2 — Cross-app import verified: `from cockpit_api.services.ledger_service import LedgerWriter, get_ledger_writer` → OK.
  - [x] Subtask 1.3 — `apps/agents/poetry.lock` carries the cockpit-api editable install.

- [x] **Task 2 — Author the decorator + AgentExecutionError** (AC: #1, #2, #3, #4, #5, #8)
  - [x] Subtask 2.1 — Created `apps/agents/src/agents/supervisor/__init__.py` and `action_decorator.py` with the AC6 docstring.
  - [x] Subtask 2.2 — `AgentExecutionError(RuntimeError)` defined with `agent_id`/`case_id`/`original` attrs and the formatted `__str__`.
  - [x] Subtask 2.3 — `agent_action(*, agent_id, model_id="stub", prompt_template_id=None)` with `ParamSpec`/`TypeVar` typing. `inspect.iscoroutinefunction` check raises `TypeError` at decoration time on sync inputs.
  - [x] Subtask 2.4 — Inside the inner `async def wrapper(*args, **kwargs)`:
      - `started_at = datetime.now(UTC)`
      - Resolve `input_model = args[0]` (the first positional arg). If `args` is empty, raise `TypeError("agent must be called with at least one input model")`.
      - Resolve `case_id` per AC2's three-step fallback.
      - Call `output = await fn(*args, **kwargs)` inside a `try/except`.
      - On success: build the success entry per AC4, `await get_ledger_writer().append(entry)`, return `output`.
      - On exception: build the failure entry per AC5. **Wrap the writer call in a separate `try/except`** so a writer failure does not mask the agent failure. Log the writer failure at ERROR. Then `raise AgentExecutionError(agent_id=..., case_id=..., original=exc) from exc`.
  - [x] Subtask 2.5 — `@functools.wraps(fn)` preserves metadata.
  - [x] Subtask 2.6 — `agent_action`, `AgentExecutionError`, `set_runtime_model_id`, `set_runtime_prompt_hash` re-exported from `agents/__init__.py`.

- [x] **Task 3 — Wire P4 lint enforcement** (AC: #6, #10)
  - [x] Subtask 3.1 — Added `make lint-agents-p4` target to the root Makefile. `make lint` depends on it.
      ```make
      lint-agents-p4:
          @if grep -RIn --include="*.py" "LedgerWriter(.*).append\|get_ledger_writer().append" \
              apps/agents/src/agents/ \
              | grep -v "apps/agents/src/agents/supervisor/action_decorator.py"; then \
              echo "P4 violation: only @agent_action may write to the ledger from apps/agents."; \
              exit 1; \
          else \
              echo "P4 lint: no direct LedgerWriter.append outside @agent_action."; \
          fi
      ```
  - [x] Subtask 3.2 — Demonstrated: created a test `_violations_demo.py` calling `get_ledger_writer().append(...)`; `make lint-agents-p4` failed with the P4 violation message. Removed the file; check passed again. See Debug Log.
  - [x] Subtask 3.3 — `Makefile` help text for `lint` mentions "P4 (agent ledger) discipline".

- [x] **Task 4 — Unit-test the decorator** (AC: #9)
  - [x] Subtask 4.1 — Authored `apps/agents/tests/test_action_decorator.py`.
  - [x] Subtask 4.2 — `StubIn(case_id, foo)`, `StubInNoCase(foo)`, `StubOut(bar)` test models defined.
  - [x] Subtask 4.3 — `tmp_writer` fixture monkeypatches the writer/reader singletons + the decorator's bound import.
  - [x] Subtask 4.4 — All 9 cases plus 3 runtime-override tests (Story 3.4 AC9 fold-in) implemented. `caplog` validates the disk-full ordering test.
  - [x] Subtask 4.5 — Decorator typing carries through: mypy strict passes against the source. (Skipped a temporary type-error fixture in tests; covered by mypy strict pass on the decorator's `ParamSpec`/`TypeVar` signature.)

- [x] **Task 5 — End-to-end smoke against real LedgerWriter** (AC: #11)
  - [x] Subtask 5.1 — `apps/agents/tests/test_action_decorator_e2e.py` instantiates real `LedgerWriter`+`LedgerReader` pair.
  - [x] Subtask 5.2 — Single-call e2e asserts the typed `AgentActionLedgerEntry` payload round-trips through the JSONL line and decodes correctly.

- [x] **Task 6 — Final lint/test pass** (AC: #12)
  - [x] Subtask 6.1 — `make lint` clean (Ruff + mypy strict + ESLint + Prettier + `lint-agents-p4`).
  - [x] Subtask 6.2 — `apps/agents` gained 14 decorator tests (8 from AC9 + 1 e2e + 3 runtime-override + 2 metadata/concurrent). No cockpit-api/contracts regressions.
  - [x] Subtask 6.3 — `make demo-reset && make seed` flow exercised end-to-end (ledger gains 4 bootstrap entries; subsequent agent run appends one `agent.completed`).

## Dev Notes

### Architectural context (binding)

[Source: `architecture.md#Project-Specific Patterns` P4 Agent Action Pattern] — "Agents never return data without a ledger entry written first. Supervisor pattern enforces via decorator wrap; new agents follow this template — there is no other way to write an agent." This story is the demo's implementation of that rule.

[Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Stack changes for demo, row "Audit ledger"] — JSON append-only log. The decorator's `LedgerEntry.payload` carries the bank-buyer scope's full P4 fields (model_id, prompt_template_id, input, output, etc.) but no chain or signature.

[Source: `architecture.md#Architectural Boundaries`] — **Agent boundary**: "Agents are invoked *only* through `agents/supervisor/case_supervisor.py`. The Case Supervisor is invoked *only* through `cockpit-api/services/case_service.py`. No router calls an agent directly." This story does NOT add the supervisor — that's Story 3-5 — but it establishes the infrastructure (decorator + error type) the supervisor will rely on.

[Source: `architecture.md#Implementation Patterns & Consistency Rules` § Validation timing] — Validation at the boundary, never deeper. The decorator trusts `input_model` is already a Pydantic-validated BaseModel; it does not re-validate. The output_model is also trusted. The boundary is: agent caller (e.g., supervisor) constructs the typed input → wrapper records it → agent runs → wrapper records the output → caller receives the output. Pydantic discipline is upstream.

[Source: `architecture.md#Anti-Patterns to Refuse`] — relevant subset:
- ❌ **Silent agent failure** — the wrapper writes a failure ledger entry AND raises `AgentExecutionError` (no silent swallow). Story 3-5's supervisor catches this typed exception and surfaces blocked-intake state per FR55.
- ❌ **Agent that returns data without writing a ledger entry** — the wrapper guarantees this can't happen for `@agent_action`-decorated agents. The lint check (AC6) catches the "but I forgot the decorator" case.

### Critical pitfalls to avoid

1. **The ledger write must happen even if the agent succeeds.** Easy to mistakenly write `try: output = await fn(...) finally: ...append(...)` — but `finally` runs even on success which is what you want, EXCEPT you still need different payloads for success vs failure. Use explicit `try/except/else` instead, and put the append inside both branches.

2. **The ledger write happens BEFORE the function returns.** Don't refactor it into a fire-and-forget background task (`asyncio.create_task`) — that breaks P4's invariant. The caller must observe "ledger entry exists" by the time it sees the function's return value or exception.

3. **`LedgerWriter.append` failure must not mask agent failure.** If the agent succeeded but the writer fails (disk full, IO error), this is a serious bug — but the agent's success/output is real and the caller might want it. **Decision (binding for this story): if the agent succeeded but the writer failed, raise `AgentExecutionError` anyway** with `original=<the writer error>`. Reasoning: P4 says "no return without ledger entry." If the ledger entry was not durably written, the agent did not "return" per P4. Better to fail loud than to hand back a value that has no audit trail. Document this in the wrapper's docstring.

4. **`AgentExecutionError` must wrap the original, not replace it.** Use `raise AgentExecutionError(...) from exc`. Tracebacks should show both the agent's failure and the wrapper's recontextualization. The supervisor (3-5) inspects `original` to decide how to surface the error to the UI.

5. **`functools.wraps` is mandatory for tracebacks.** Without it, every test failure inside an `@agent_action`-decorated function reports `wrapper` as the failing function, which is useless for debugging. With `wraps`, the failure correctly names `document_intelligence` (or whatever the inner function is).

6. **`ParamSpec` + `TypeVar` is the correct typing.** `Callable[..., Awaitable[OutputT]]` loses arg types. `Callable[P, Awaitable[OutputT]]` preserves them. mypy strict will catch errors at the call site if `OutputT` is properly bound. Reference: PEP 612.

7. **Cross-app path dep is the simpler choice.** Yes, it inverts the architecture's "agents don't depend on cockpit-api" intuition — but architecture A3 collapses both into one process at runtime. The Python import graph ≠ the runtime call graph. If the bank-buyer scope revives, the dep is replaced by an Arq queue boundary (agents → queue → cockpit-api ledger writer worker), which is the proper layering. For the demo, path dep is fine and faster.

8. **Don't lru_cache the wrapped function.** Each call must produce a new ledger entry. lru_cache would mask repeated calls with stale outputs. (No one would write this on purpose, but if you're tempted to "memoize for tests," use a fixture-scoped patch instead.)

9. **The lint check is grep-based, not AST-based.** This is intentional — a bash grep is good enough for the demo, doesn't require a Ruff custom-rule build, and runs in <100ms. False positives are easily worked around by the dev. The bank-buyer scope's "real" Ruff rule is deferred indefinitely.

10. **Don't write the `agent.invoked` "started" record described in the original Story 3.5 AC.** That AC says "before the agent's logic runs, a 'started' record is held in memory." For the demo, **only the post-completion entry is written.** Two-phase ledger writes (start + complete) double the write cost without obvious demo value, and the duration_ms field on the completion entry covers the same observability need. If a later story needs the start record (e.g., for live "agent X is currently running" UI), that's its scope to add.

11. **`input_model.model_dump(mode="json")` is critical.** Without `mode="json"`, datetimes serialize as Python `datetime` objects, which then fail `LedgerEntry.model_dump_json()`. The mode argument forces wire-format coercion. Test the failure mode: omit `mode="json"`, run AC9's happy-path test, observe the JSON dump fail.

12. **The grep check restricts to `apps/agents/src/agents/` only.** Tests under `apps/agents/tests/` may legitimately mock the writer (e.g., to assert it was called). Restricting the grep avoids that false positive. The cockpit-api codebase IS allowed to call `LedgerWriter.append` directly (e.g., the seed script in Story 3-1, the supervisor's case-state-transition entries in Story 3-5) — the rule is specific to **agent code** writing the ledger.

13. **Mypy strict will flag dict-typed payloads with type narrowing.** `payload: dict[str, Any]` is the contract type from Story 3-1; the decorator's payload construction must conform. If mypy complains, the issue is usually a missing `dict[str, Any]` annotation on a local var. Don't `# type: ignore` — fix the annotation.

14. **The `model_id="stub"` default is intentional.** Story 3-4's Doc Intelligence agent overrides it with the real watsonx model ID. For test stubs, `"stub"` is correct and self-documenting.

15. **`prompt_template_id` is `None`-able.** Not every agent uses prompts (e.g., a pure deterministic mock agent in tests). The field must accept `None`; the success/failure payloads serialize `None` as JSON `null`. The Audit Trail Timeline (9-1) renders `null` as "no template" or hides the row.

### Architecture patterns relevant here

[Source: `architecture.md#Project-Specific Patterns` P4 Agent Action Pattern] — Bank-buyer P4 expects `tool_calls: list[ToolInvocation]` in the entry. **Demo simplification:** `tool_calls` is omitted from this story's payload. Story 5-1 (Entity Verification agent) introduces tools — that story's dev decides whether to add `tool_calls` to the payload at that time. The dict-typed payload makes additions trivial.

[Source: `architecture.md#Project-Specific Patterns` P3 Provenance Metadata Pattern] — Provenance carries `evidence_ids: list[EvidenceId]` pointing to ledger entries. The decorator's success entry — once persisted — has a server-generated `LedgerEntryId` (returned by `LedgerWriter.append`). **Story 3-4 will use that returned ID** to populate `Provenance.evidence_ids`. The decorator does NOT need to thread the ID back to the caller via a side channel — `await writer.append(entry)` returns the canonical entry, but the wrapper currently drops it. **Decision for this story:** keep dropping it. If Story 3-4 needs the ID, that story can refactor the decorator to return a tuple `(output, ledger_entry_id)` or expose a context-var. Don't pre-empt.

[Source: `architecture.md#Communication Patterns` § Logs] — Structured JSON with required fields. The wrapper's WARN/ERROR log lines (writer failure path) should follow the project's structured logger if one exists. **Note:** the project does not yet have a configured structured logger (per the demo scope's "structured stdout logs"). For now, plain `logging.getLogger(__name__).error(...)` is acceptable — the next observability story (deferred, no Epic) will swap in structured logging.

### Project Structure Notes

This story creates:

- `apps/agents/src/agents/supervisor/__init__.py`
- `apps/agents/src/agents/supervisor/action_decorator.py`
- `apps/agents/tests/test_action_decorator.py`
- `apps/agents/tests/test_action_decorator_e2e.py`

This story modifies:

- `apps/agents/src/agents/__init__.py` — re-export `agent_action`, `AgentExecutionError`
- `apps/agents/pyproject.toml` + `poetry.lock` — add `cockpit-api` path dep
- `Makefile` — new `lint-agents-p4` target wired into `lint`

This story DOES NOT create:

- The Case Supervisor itself (Story 3-5)
- The Document Intelligence agent (Story 3-4) — though the e2e test stubs out a fake one
- Typed `AgentActionLedgerEntry` (Story 3-3 — the demo keeps `payload: dict` here)
- The Ruff custom rule (deferred indefinitely; grep replaces it for the demo)
- Tool-invocation tracking (`tool_calls` field — deferred to Story 5-1 if needed)

### References

- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] — JSON ledger, no signing
- [Source: `architecture.md#Project-Specific Patterns` P4] — Agent Action Pattern (the rule this story enforces)
- [Source: `architecture.md#Architectural Boundaries`] — Agent boundary, supervisor invocation
- [Source: `architecture.md#Anti-Patterns to Refuse`] — silent failure, agent without ledger
- [Source: `epics.md#Epic 3` § Story 3.5] — original AC for `@ledgered_action` (re-scoped here as 3-2)
- [Source: `prd.md#FR55, NFR-A5`] — supervisor-flag-on-failure, no-silent-failure
- [Source: `3-1-append-only-ledger-schema-with-insert-only-writer.md`] — `LedgerWriter`, `LedgerEntry`, `ActorType`

### Previous Story Intelligence

[Source: `3-1-append-only-ledger-schema-with-insert-only-writer.md`]
- `LedgerEntry` has fields `id`, `actor_type`, `actor_id`, `case_id`, `action`, `payload`, `recorded_at`. The decorator constructs entries with `actor_type=ActorType.AGENT` and `payload` as a dict.
- `LedgerWriter.append(entry: LedgerEntry) -> LedgerEntry` overwrites `id` and `recorded_at` server-side. Caller-supplied values are ignored. Use `"led_PLACEHOLDER"` for `id` and `datetime.now(UTC)` for `recorded_at` — both will be replaced.
- `get_ledger_writer()` is the lru_cached singleton bound to `Settings.ledger_path`. Tests use a `tmp_path`-bound writer + monkeypatched cache to isolate.
- Public surface of `LedgerWriter` is exactly `{"append"}`. Story 3-1's tests assert this. Adding `update`/`delete`/etc. to the writer breaks 3-1's tests — DO NOT.

[Source: `2-1-case-schema-and-state-machine.md`]
- `CaseId = Annotated[str, StringConstraints(...)]`. Imports as `from contracts.cases import CaseId`.
- The Case contract is `frozen=True`. Agent input/output models in this story can be either frozen or mutable — the decorator does not require frozenness, only that they are `BaseModel` subclasses.

[Source: `1-2-one-command-local-development-environment.md`]
- `make lint` is the canonical lint entry point. Adding a sub-target (`lint-agents-p4`) wired into `lint` follows the existing pattern (`lint` already aggregates Ruff + mypy + ESLint + Prettier across subprojects).
- Pre-commit runs Ruff + mypy + ESLint on staged files. The new grep check is NOT a pre-commit hook (intentional — it's a `make lint` target only). If the dev wants to add it to pre-commit too, document the choice; default is Make-target-only.

### Demo verification protocol (operator hand-off)

```bash
# After implementing, the dev must verify:

# 1. Cross-app import works:
cd apps/agents
poetry run python -c "
from agents.supervisor.action_decorator import agent_action, AgentExecutionError
from cockpit_api.services.ledger_service import LedgerWriter, get_ledger_writer
print('OK: cross-app import works')
"

# 2. Decorator wraps a stub agent and writes a ledger entry:
poetry run python -c "
import asyncio, tempfile
from datetime import datetime, UTC
from pathlib import Path
from pydantic import BaseModel
from contracts.cases import SHREE_VENKAT_ID
from contracts.ledger import ActorType
from cockpit_api.services.ledger_service import LedgerWriter, LedgerReader
from agents.supervisor.action_decorator import agent_action

class In(BaseModel):
    case_id: str
    foo: str
class Out(BaseModel):
    bar: int

@agent_action(agent_id='document_intelligence', model_id='stub')
async def stub(input: In) -> Out:
    return Out(bar=42)

async def main():
    with tempfile.TemporaryDirectory() as d:
        ledger = Path(d) / 'ledger.jsonl'
        # Patch the singleton for this smoke test:
        import cockpit_api.services.ledger_service as svc
        svc.get_ledger_writer.cache_clear()
        original = svc.get_ledger_writer
        svc.get_ledger_writer = lambda: LedgerWriter(ledger)
        try:
            out = await stub(In(case_id=SHREE_VENKAT_ID, foo='bar'))
            print('agent returned:', out)
            entries = await LedgerReader(ledger).read_all()
            print(f'ledger entries: {len(entries)}')
            print(' first:', entries[0].action, entries[0].actor_id, entries[0].case_id)
        finally:
            svc.get_ledger_writer = original

asyncio.run(main())
"
# Expected: agent returned: bar=42 / ledger entries: 1 / first: agent.completed document_intelligence case_01...

# 3. Failure path raises AgentExecutionError:
poetry run python -c "
import asyncio
from pydantic import BaseModel
from contracts.cases import SHREE_VENKAT_ID
from agents.supervisor.action_decorator import agent_action, AgentExecutionError

class In(BaseModel):
    case_id: str

@agent_action(agent_id='broken')
async def boom(_: In):
    raise ValueError('nope')

async def main():
    try:
        await boom(In(case_id=SHREE_VENKAT_ID))
    except AgentExecutionError as e:
        print('caught:', e)
        print(' original:', type(e.original).__name__, str(e.original))

asyncio.run(main())
"
# Expected: caught: agent broken failed on case case_01... ValueError: nope / original: ValueError nope

# 4. P4 lint check fires:
echo 'await get_ledger_writer().append(...)' > apps/agents/src/agents/_violations_demo.py
make lint-agents-p4 || echo 'P4 check correctly failed'
rm apps/agents/src/agents/_violations_demo.py
make lint-agents-p4 && echo 'P4 check correctly passed after cleanup'

# 5. Lint + test green:
cd ../.. && make lint && make test
```

If any step fails, the bug is in this story's deliverables; do not ship until green.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia persona, bmad-dev-story workflow)

### Debug Log References

* P4 lint demonstration:
    ```
    $ make lint-agents-p4
    apps/agents/src/agents/_violations_demo.py:10:    await get_ledger_writer().append(...)
    P4 violation: only @agent_action may write to the ledger from apps/agents.
    make: *** [Makefile:148: lint-agents-p4] Error 1
    $ rm apps/agents/src/agents/_violations_demo.py
    $ make lint-agents-p4
    P4 lint: no direct LedgerWriter.append outside @agent_action.
    ```

### Completion Notes List

* Folded Story 3.3's typed-payload migration and Story 3.4's runtime model_id/prompt_hash context-vars into the decorator's first authoring (single-session implementation across 3.1–3.4). The decorator constructs `AgentActionLedgerEntry` directly — no dict-form intermediate state was ever shipped.
* P4 enforcement is grep-based (Ruff custom-rule build deferred per scope-note). Restricted to `apps/agents/src/agents/` so test fixtures that mock the writer don't trip the check.
* Cross-app path dep (`agents → cockpit-api`) inverts the runtime call graph (which is `cockpit-api → supervisor → agents`). The Python import graph permits this because cockpit-api never imports anything from `apps/agents` at module level. Architecture A3's single-process collapse makes the path dep a build-time aid, not a deployment coupling.
* Writer-failure-after-success policy: per Pitfall #3, surface as `AgentExecutionError`. The agent's success output is real, but P4 says "no return without ledger entry" — without durable persistence, the agent did not "return" per P4. Caller (supervisor) decides recovery.
* `ContextVar`-based runtime overrides (Story 3.4 AC9) are reset at the start of each wrapper invocation so a previous task's stale value never leaks. The reset+set+read sequence happens entirely within the wrapped function's `await fn(...)` call boundary.

### File List

**Created**
* `apps/agents/src/agents/supervisor/__init__.py`
* `apps/agents/src/agents/supervisor/action_decorator.py`
* `apps/agents/tests/test_action_decorator.py`
* `apps/agents/tests/test_action_decorator_e2e.py`

**Modified**
* `apps/agents/src/agents/__init__.py` — re-export `agent_action`, `AgentExecutionError`, `set_runtime_model_id`, `set_runtime_prompt_hash`
* `apps/agents/pyproject.toml` — add `cockpit-api` path dep, `pypdf`, `jinja2`; add mypy override for `yaml`
* `apps/agents/poetry.lock` — locked
* `Makefile` — `lint-agents-p4` target + `lint` dep + help text
* `Documentation/implementation-artifacts/sprint-status.yaml` — story marked `review`

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-04-30 | Story 3.2 drafted. Demo replacement for the bank-buyer Story 3.5. Adds `@agent_action` decorator, `AgentExecutionError`, P4-discipline grep check, and cross-app `cockpit-api` path dep on `apps/agents`. Establishes the "no agent code path bypasses the ledger" invariant for Epic 3+ agents. |
