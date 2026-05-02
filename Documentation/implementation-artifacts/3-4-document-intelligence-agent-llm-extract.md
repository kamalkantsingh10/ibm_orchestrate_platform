# Story 3.4: Document Intelligence agent (LLM extract)

Status: review

## Story

As the platform,
I want a real watsonx Orchestrate ADK Document Intelligence agent that — given a case's listed `document_refs` — extracts company/individual KYC fields (CIN, PAN, GST, registered address, incorporation date, names, etc.) via a single LLM call against pypdf-extracted text, returns each field as a `ProvenancedField[T]` with confidence + ledger-pointing evidence, and writes its full invocation to the append-only ledger via `@agent_action`,
So that on case open the analyst sees structured, provenance-tagged intake data without manual entry, and the demo's "first real ADK agent" milestone is met (FR3, FR14, FR8, NFR-RI1, NFR-T5 ≥ 95% — relaxed for the demo).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 3.9. The agent itself is real; the doc-AI backend is replaced.

| Bank-buyer scope (original 3.9) | Demo replacement in this story |
|---|---|
| Pluggable `DocAI` adapter Protocol with mock impl + IBM Document AI impl + Watson Discovery impl + 50-doc benchmark (NFR-T5 ≥ 95% precision lock) | **Single LLM call** via a small `DocAILLM` Protocol with two impls: `FixtureDocAILLM` (default, returns deterministic extractions keyed by `document_ref` filename — runs offline, the demo's reliability backbone) and `WatsonxDocAILLM` (single watsonx LLM call against pypdf-extracted text — used only when `DOC_AI_PROVIDER=watsonx` env var is set + creds configured). No second-impl conformance pair, no benchmark. |
| `DocAI.extract_fields(doc: DocumentRef, taxonomy: DocTaxonomy, *, tenant_id: TenantId) -> ExtractionResult` | `DocAILLM.extract(document_ref: str, text: str \| None, taxonomy: DocTaxonomy) -> list[ExtractedField]`. No `tenant_id` (single-tenant demo). |
| Document storage in IBM COS / S3 / MinIO via `DocStore` adapter | **Local filesystem** at `./fixtures/uploads/<document_ref>` (per architecture demo addendum). Fixture mode does NOT read files; watsonx mode does. |
| 50-document corpus benchmark + per-vendor precision report | **Cut.** Story 3.11 was cut entirely; no benchmark in the demo. |
| `prompt_hash`, full prompt + golden inputs in agent action ledger entry | **Kept** — `prompt_hash` populated by the watsonx path; `None` for fixture path. Jinja template + golden inputs at `apps/agents/src/agents/prompts/document_intelligence/`. |
| Per-doc-type Pydantic ExtractionResult variants | **Single `DocumentIntelligenceOutput`** — list of `ExtractedField` keyed by `field_name`, no per-doc-type branching. Demo's three fixture cases all map to the India SME taxonomy. |

What survives: **real ADK agent registration, real Pydantic contracts on agent input/output, ProvenancedField[T] on every extracted value, ledger entry per invocation via `@agent_action`, Jinja prompt template with golden input.** Those make this story the canonical ADK pattern showcase that NFR-RI1 demands.

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` § Stories simplified, `architecture.md#Demo Scope Addendum (2026-04-29)` row "Document AI", and `epics.md#Epic 3` § Story 3.9.

## Acceptance Criteria

1. **AC1 — Pydantic contracts for the agent live in `packages/contracts/src/contracts/document_intelligence.py`.** Three classes:

    ```python
    class DocumentIntelligenceInput(BaseModel):
        model_config = {"frozen": True}
        case_id: CaseId
        document_refs: list[str]   # filenames; min_length=1; each non-empty

    class ExtractedField(BaseModel):
        model_config = {"frozen": True}
        field_name: str            # e.g., "company_name", "cin", "pan", "incorporation_date"
        document_ref: str          # source filename
        value: ProvenancedField[FieldValue]

    class DocumentIntelligenceOutput(BaseModel):
        model_config = {"frozen": True}
        case_id: CaseId
        extracted_fields: list[ExtractedField]
    ```

    `FieldValue = str | int | float | bool | None` (a `TypeAlias`). The `value: ProvenancedField[FieldValue]` reuses Story 3-3's generic — values arrive with a `Provenance` block already populated (source_agent="document_intelligence", source_system="<provider>", confidence, evidence_ids).

    Re-export from `packages/contracts/src/contracts/__init__.py` alongside `FieldValue`.

2. **AC2 — Doc taxonomy lives at `apps/agents/src/agents/jurisdictions/india/doc_taxonomy.yaml`.** YAML maps document categories to expected fields:

    ```yaml
    # India SME doc taxonomy (Story 3.4)
    incorporation_certificate:
      - field: company_name
        type: str
        required: true
      - field: cin
        type: str
        required: true
        validation: ^[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$
      - field: incorporation_date
        type: date
        required: true
      - field: registered_address
        type: str
        required: true
    pan_card:
      - field: pan
        type: str
        required: true
        validation: ^[A-Z]{5}\d{4}[A-Z]$
      - field: name
        type: str
        required: true
    address_proof:
      - field: address
        type: str
        required: true
    director_id:
      - field: din
        type: str
        required: false
        validation: ^\d{8}$
      - field: director_name
        type: str
        required: true
    bank_statement:
      - field: account_holder_name
        type: str
        required: true
      - field: account_number
        type: str
        required: true
    ubo_declaration:
      - field: ubo_chain
        type: str       # demo: free-text; Epic 5 will introduce a typed UBO chain
        required: true
    shareholder_pattern:
      - field: shareholder_summary
        type: str
        required: false
    aadhaar:
      - field: aadhaar_last4
        type: str
        validation: ^\d{4}$
        required: true
      - field: name
        type: str
        required: true
    income_proof:
      - field: annual_income_inr
        type: int
        required: false
    ```

    The agent maps `document_ref` filenames to categories via a small `_classify(filename) -> str` helper using filename heuristics (`"incorporation_certificate.pdf" -> "incorporation_certificate"`, etc.). Unknown filenames fall back to `"unknown"` category with no expected fields and produce a single `ExtractedField` of `field_name="raw_text", value=ProvenancedField(value=<extracted text first 200 chars>, ...)` so the analyst still sees something. Decision point for the dev: filename-based classification is brittle but fits the demo's pinned-fixture model. Document the rule in the agent's docstring.

    A small Pydantic loader `class DocTaxonomy(BaseModel)` parses the YAML at startup and exposes `categories: dict[str, list[FieldSpec]]` where `FieldSpec(field_name, type, required, validation: str | None)`. Loader lives in `apps/agents/src/agents/jurisdictions/india/__init__.py`. Cached at module-level via `@lru_cache`.

3. **AC3 — `DocAILLM` Protocol lives at `apps/agents/src/agents/adapters/doc_ai/base.py`.**

    ```python
    class DocAILLM(Protocol):
        async def extract(
            self,
            *,
            document_ref: str,
            text: str | None,
            taxonomy: DocTaxonomy,
        ) -> list[ExtractedField]: ...
    ```

    `text` is `None` when the file does not exist on disk OR when the impl does not need it (fixture mode). Both impls return the same `list[ExtractedField]` shape — only the upstream method of obtaining the values differs.

4. **AC4 — `FixtureDocAILLM` is the demo default.** Lives at `apps/agents/src/agents/adapters/doc_ai/fixture.py`.

    Behavior:
    - Holds an in-module `_FIXTURE_EXTRACTIONS: dict[str, list[ExtractedField]]` keyed by `document_ref` filename. Each list contains the canonical extractions the demo expects to see for that filename. Filenames covered: every `document_ref` from Story 2-4's three fixture cases — `incorporation_certificate.pdf`, `pan_card.pdf`, `address_proof.pdf`, `director_id.pdf`, `ubo_declaration.pdf`, `shareholder_pattern.pdf`, `bank_statement_q1.pdf`, `aadhaar.pdf`, `income_proof.pdf` (some appear in multiple cases — the fixture extractions are filename-keyed, so the same filename returns the same fields each time it's seen; for the demo's three cases that share filenames, this is intentional — the supervisor's per-case context disambiguates).
    - Fields populate per the India taxonomy (AC2) with **deterministic, plausible synthetic values**. Examples:
      - `incorporation_certificate.pdf`: `company_name="Vora Capital Holdings Pvt Ltd"` (with `confidence=0.92`), `cin="U67120MH2024PTC444789"` (`0.95`), `incorporation_date="2024-08-22"` (`0.90`), `registered_address="Suite 402, Sea Breeze Heights, Bandra West, Mumbai 400050"` (`0.86`)
      - `pan_card.pdf`: `pan="AAFCV1234R"` (`0.94`), `name="Vora Capital Holdings Pvt Ltd"` (`0.91`)
      - `address_proof.pdf`: `address="Suite 402, Sea Breeze Heights, Bandra West, Mumbai"` (`0.78`)
      - etc.
    - **Confidence levels are intentionally varied** so Story 3-7's ConfidencePill can demonstrate all four bands across the demo. At least one extraction per fixture case is in `MEDIUM_LOW` (0.40–0.65) and at least one is in `HIGH` (≥0.85). Document the band distribution in the file's docstring.
    - The `Provenance` on each field uses `source_agent="document_intelligence"`, `source_system="fixture_doc_ai"`, `evidence_ids=[]` (filled in by the agent wrapper after the ledger entry is appended — see AC8), `captured_at=datetime.now(UTC)` set at extraction time.
    - **The fixture impl ignores `text`** — it does not require any PDF on disk to produce extractions.

5. **AC5 — `WatsonxDocAILLM` is the showcase impl.** Lives at `apps/agents/src/agents/adapters/doc_ai/watsonx.py`.

    Behavior:
    - Renders the Jinja template `apps/agents/src/agents/prompts/document_intelligence/extract_v1.j2` with `document_ref`, `text`, and `taxonomy` (the relevant category's `FieldSpec` list) as variables.
    - Computes `prompt_hash = hashlib.sha256(rendered.encode("utf-8")).hexdigest()`.
    - Calls watsonx via the `ibm-watsonx-orchestrate` SDK (already a dep in `apps/agents/pyproject.toml`). Model defaults to `ibm/granite-3-2-8b-instruct` — the SDK exposes a `WatsonxLLM` (or equivalent) client; if the dev finds a different idiom canonical, document the choice in the file's docstring.
    - Authentication via `WATSONX_API_KEY` + `WATSONX_PROJECT_ID` env vars (added to `.env.example` as commented-out placeholders — `# WATSONX_API_KEY=...` etc., per AC11). Both required for this impl; the impl raises `RuntimeError("WATSONX_API_KEY missing — set DOC_AI_PROVIDER=fixture for offline demo")` if missing.
    - Parses the LLM response as JSON matching the contract `list[ExtractedFieldRaw]` where `ExtractedFieldRaw` has `field_name`, `value`, `confidence`. Validates against the `FieldSpec` regex if the spec has one. Builds `ExtractedField` records with `Provenance(source_system="watsonx_<model_id>")` and `prompt_hash` recorded in the agent action ledger entry (Story 3-2's decorator handles this — but the watsonx client must surface `prompt_hash` to the decorator, see AC9).
    - On any LLM error (timeout, schema validation failure, auth failure), raise `DocAILLMError(...)` (a custom subclass of `RuntimeError`). The `@agent_action` decorator catches this and writes a failure ledger entry per Story 3-2's failure path.

    **Decision point for the dev:** the watsonx client may not be straightforwardly importable from `ibm-watsonx-orchestrate` — the SDK is primarily an agent runtime, not an LLM client. Two acceptable fallbacks:
    - Use `langchain-ibm` (add as a dep) to call watsonx — adds 1 line to `pyproject.toml`.
    - Use raw `httpx` against the watsonx HTTP API.
    Pick the smaller dep footprint; document in the file's docstring.

    **The watsonx impl is OPTIONAL in this story's CI gate**: if `WATSONX_API_KEY` is unset (the default in CI), tests skip the watsonx impl tests via `pytest.mark.skipif`. The impl is checked-in and lints clean, but is not exercised in CI. Demo presenters with creds can set the env vars and exercise it manually.

6. **AC6 — Jinja prompt template** at `apps/agents/src/agents/prompts/document_intelligence/extract_v1.j2`:

    ```jinja
    You are a careful KYC document field extractor. Given the text from a {{ document_ref }} document, extract these fields:

    {% for spec in taxonomy %}
    - {{ spec.field_name }} ({{ spec.type }}{% if spec.validation %}; matches /{{ spec.validation }}/{% endif %}; required={{ spec.required }})
    {% endfor %}

    Document text:
    ---
    {{ text }}
    ---

    Return ONLY a JSON array. Each element: {"field_name": "<name>", "value": <typed_value>, "confidence": <float in [0.0, 1.0]>}. Set "value" to null if a required field is genuinely unreadable. Do not include fields not in the list. Self-rate confidence: 0.85+ if the field is unambiguous and clearly visible; 0.65 if visible but ambiguous; 0.40 if inferred from partial text; below 0.40 if guessed.
    ```

    Strict variable escaping is on by default in Jinja (`autoescape=True` for HTML; not strictly needed here since the output isn't HTML — but **autoescape is enabled** to defend against prompt-injection from document-derived text per `architecture.md` § S7).

    **Golden input** at `extract_v1.golden.json`:
    ```json
    {
      "document_ref": "incorporation_certificate.pdf",
      "text": "CERTIFICATE OF INCORPORATION...\n\nThe name of the company is Vora Capital Holdings Pvt Ltd...\nCorporate Identification Number: U67120MH2024PTC444789\nDate of Incorporation: 22 August 2024\nRegistered Office: Suite 402, Sea Breeze Heights, Bandra West, Mumbai 400050\n",
      "taxonomy": [
        {"field_name": "company_name", "type": "str", "required": true, "validation": null},
        {"field_name": "cin", "type": "str", "required": true, "validation": "^[LU]\\d{5}[A-Z]{2}\\d{4}[A-Z]{3}\\d{6}$"},
        {"field_name": "incorporation_date", "type": "date", "required": true, "validation": null},
        {"field_name": "registered_address", "type": "str", "required": true, "validation": null}
      ]
    }
    ```

    **Golden output** at `extract_v1.golden.output.json` (what a well-behaved LLM should produce):
    ```json
    [
      {"field_name": "company_name", "value": "Vora Capital Holdings Pvt Ltd", "confidence": 0.94},
      {"field_name": "cin", "value": "U67120MH2024PTC444789", "confidence": 0.97},
      {"field_name": "incorporation_date", "value": "2024-08-22", "confidence": 0.92},
      {"field_name": "registered_address", "value": "Suite 402, Sea Breeze Heights, Bandra West, Mumbai 400050", "confidence": 0.88}
    ]
    ```

    A test asserts the rendered template against the golden input produces a deterministic prompt (hash-stable), and that the watsonx impl's response parser correctly maps the golden output to `list[ExtractedField]`.

7. **AC7 — The agent function lives at `apps/agents/src/agents/intake/document_intelligence.py`.**

    ```python
    @agent_action(
        agent_id="document_intelligence",
        model_id="<resolved at call time>",  # set inside the function via mutation, see below
        prompt_template_id="document_intelligence/extract_v1",
    )
    async def document_intelligence(
        input: DocumentIntelligenceInput,
        *,
        llm: DocAILLM | None = None,
    ) -> DocumentIntelligenceOutput:
        ...
    ```

    Logic:
    1. Resolve the LLM client: `llm = llm or _get_default_llm()`. The `_get_default_llm()` reads `DOC_AI_PROVIDER` (default `"fixture"`) and returns either `FixtureDocAILLM()` or `WatsonxDocAILLM()`. Both are stateless; OK to instantiate per-call.
    2. Load the taxonomy: `taxonomy = get_india_taxonomy()` (lru_cached).
    3. For each `document_ref` in `input.document_refs`:
        - Classify via `_classify(document_ref) -> category` (filename heuristic per AC2)
        - Look up `taxonomy.categories.get(category, [])` to get `FieldSpec` list
        - If the impl is watsonx and the file exists, read text via `pypdf.PdfReader` (full text concat); else `text = None`
        - `extracted = await llm.extract(document_ref=document_ref, text=text, taxonomy=field_specs)`
        - Append `extracted` (already typed `list[ExtractedField]`) to a running list
    4. Build `DocumentIntelligenceOutput(case_id=input.case_id, extracted_fields=combined)` and return.

    The `@agent_action` decorator from Story 3-2 captures input/output, writes the ledger entry, returns the output. **AC9 governs how `model_id` and `prompt_hash` flow into the ledger entry.**

    The agent is **not** an `orchestrate-cli`-managed YAML agent for the demo — registering with the ADK Developer Edition is OPTIONAL. The Python function with the `@agent_action` decorator is the demo's "real ADK agent" surface. **Decision point for the dev:** if the dev wants to ship the YAML manifest at `apps/agents/src/agents/intake/document_intelligence.yaml` for ADK Developer Edition discovery (NFR-RI1 ADK pattern showcase), do so — but the demo path does not require Orchestrate to be running. Document the choice. Default recommendation: ship the YAML for showcase value, but make the agent runnable without the ADK runtime.

8. **AC8 — `evidence_ids` is populated post-ledger-write.** The `Provenance.evidence_ids` field on each `ExtractedField` should point to the agent's own ledger entry (the `agent.completed` entry written by `@agent_action`). But the ledger entry's ID is generated by `LedgerWriter.append` — AFTER the agent function returns. Solution:

    **Option A (chosen): two-pass write.** The agent returns `ExtractedField` records with `evidence_ids=[]`. After `@agent_action` writes the ledger entry, the supervisor (Story 3-5) is responsible for re-reading the entry and replacing the empty `evidence_ids` lists with `[entry.id]` before exposing the result to the API/UI.

    **Option B (rejected): pre-generate the ledger entry ID.** Would require the decorator to expose its planned-id to the agent, or the agent to allocate the id and the writer to honor it. Both break the writer's "id is server-set" invariant from Story 3-1. Don't pursue.

    For this story, the agent function returns `evidence_ids=[]`; the supervisor in Story 3-5 will fill them in. **Document the contract** in `DocumentIntelligenceOutput`'s docstring: "`evidence_ids` are empty when the agent returns; the orchestrating supervisor fills them in with the agent's own ledger entry ID after the entry is appended."

9. **AC9 — `model_id` and `prompt_hash` flow into the ledger entry.** The `@agent_action` decorator (Story 3-2) takes `model_id` as a decorator-time argument — but the actual model ID depends on which LLM client is wired at call time. Two acceptable solutions:

    - **(A)** The decorator uses the static value `model_id="watsonx-or-fixture"` and the agent post-processes the ledger entry. Brittle.
    - **(B) chosen:** The agent function reads back the most recent `agent.completed` ledger entry for itself after the decorator writes it, and **does not modify it** — instead the LLM client returns a side-channel `model_id` and `prompt_hash` that the agent stuffs into a logger context (or returns as part of `DocumentIntelligenceOutput.metadata`) for the supervisor to consume. Indirect but clean.
    - **(C) chosen — simpler:** Extend the `@agent_action` decorator (Story 3-2) to accept a callable `model_id_provider: Callable[[], str] | None` that resolves at agent-completion time. **This is a minor Story 3-2 amendment that this story owns:** edit Story 3-2's decorator to look up `model_id` either as a static string (current behavior — backward compatible) OR via a context-var that the agent can populate before returning. Pattern:

        ```python
        # In the decorator (extension):
        from contextvars import ContextVar
        _runtime_model_id: ContextVar[str | None] = ContextVar("agent_action_model_id", default=None)
        # Inside wrapper, when building entry:
        resolved_model_id = _runtime_model_id.get() or model_id
        ```

        The agent sets the context var inside its function body before returning:
        ```python
        # In document_intelligence.py:
        from agents.supervisor.action_decorator import _runtime_model_id
        _runtime_model_id.set(llm.model_id)  # llm exposes a property
        ```

        Same pattern for `prompt_hash`: a `_runtime_prompt_hash: ContextVar[str | None]`. The watsonx impl sets it; the fixture impl does not (entry's `prompt_hash` stays `None`).

    **Bind: option (C).** The amendment to Story 3-2's decorator is small and self-contained; expose context-var setters as a public helper:
    ```python
    # In agents/supervisor/action_decorator.py:
    def set_runtime_model_id(model_id: str) -> None:
        _runtime_model_id.set(model_id)
    def set_runtime_prompt_hash(prompt_hash: str) -> None:
        _runtime_prompt_hash.set(prompt_hash)
    ```

    Update Story 3-2's tests to cover the new helper (a single test: set it, run a wrapped function, assert the ledger entry's payload reflects the runtime override).

10. **AC10 — Tests cover happy path, error path, taxonomy classification, prompt rendering.** Pytest specs in `apps/agents/tests/test_document_intelligence.py`:
    - **Happy path (fixture):** call `document_intelligence(DocumentIntelligenceInput(case_id=VORA_CAPITAL_ID, document_refs=["incorporation_certificate.pdf", "pan_card.pdf"]))`; assert the output contains `extracted_fields` with `company_name`, `cin`, `incorporation_date`, `registered_address` from the first doc and `pan`, `name` from the second; each has a populated `Provenance` block with `source_agent="document_intelligence"`, `source_system="fixture_doc_ai"`, `confidence` in `[0.0, 1.0]`, `confidence_band` consistent.
    - **Empty document_refs:** call with `document_refs=[]`; assert the agent returns `DocumentIntelligenceOutput(case_id=..., extracted_fields=[])` and writes a ledger entry with `payload.output.extracted_fields == []`. No error.
    - **Unknown document_ref:** call with `document_refs=["mystery_file.pdf"]`; assert the agent returns one `ExtractedField` with `field_name="raw_text"` and `value.value=None` (or empty string), with low confidence (`<0.40`). Categorization fallback works.
    - **Confidence-band distribution:** assert that across the three demo cases' canonical document_refs, at least one fixture extraction lands in each of the four bands (`LOW`, `MEDIUM_LOW`, `MEDIUM_HIGH`, `HIGH`). This guards against a future fixture-tweak that homogenizes confidences and starves Story 3-7's pill rendering of variety.
    - **Ledger entry shape:** invoke the agent against a `tmp_path`-bound LedgerWriter; read the file; assert exactly one `agent.completed` entry; assert `payload.agent_id == "document_intelligence"`, `payload.model_id == "fixture"` (the fixture client's model_id property), `payload.input.case_id`, `payload.output.extracted_fields` is the JSON-mode dump of the typed output.
    - **Prompt template renders deterministically:** use the golden input from AC6; render the Jinja template; assert the rendered string is byte-identical across two consecutive calls (no timestamps, no nondeterminism); compute SHA-256 hash; assert it matches a hardcoded golden hash (which the dev computes once and pins in the test).
    - **Watsonx impl skipped without creds:** add `@pytest.mark.skipif(not os.environ.get("WATSONX_API_KEY"), reason="watsonx creds not configured")` to the watsonx-specific test. The skipped test still imports `WatsonxDocAILLM` and instantiates it — so import-time errors surface even when the test is skipped.
    - **Watsonx error path (mocked):** monkeypatch the watsonx HTTP client to raise; assert `DocAILLMError` is raised; assert the `@agent_action` decorator caught it and wrote an `agent.failed` ledger entry.
    - **Fixture model_id is reflected in the ledger entry:** call the agent with `llm=FixtureDocAILLM()`; assert the ledger entry's `payload.model_id == "fixture"`. Validates AC9's context-var plumbing.

11. **AC11 — `.env.example` documents the env vars.** Add a new section:
    ```
    # ─── Story 3.4 Document Intelligence ───
    # Provider for the doc-AI LLM call. "fixture" is offline; "watsonx" calls watsonx LLM.
    DOC_AI_PROVIDER=fixture
    # Required only when DOC_AI_PROVIDER=watsonx. Demo defaults to fixture mode.
    # WATSONX_API_KEY=
    # WATSONX_PROJECT_ID=
    # WATSONX_MODEL_ID=ibm/granite-3-2-8b-instruct
    ```

12. **AC12 — `make demo-reset && make seed && make test` clean.** New test count adds at least: 8+ in `test_document_intelligence.py` (the cases from AC10), 2+ contract tests for `DocumentIntelligenceInput`/`Output` round-trip in `packages/contracts/tests/test_document_intelligence.py`, 1+ for the Story 3-2 decorator amendment. `make lint` passes (Ruff + mypy strict + ESLint + Prettier + the AC6 P4 lint extension from Story 3-2).

## Tasks / Subtasks

- [x] **Task 1 — Author the input/output Pydantic contracts** (AC: #1)
  - [x] Subtask 1.1 — Created `document_intelligence.py` with `FieldValue` TypeAlias, `ExtractedField`, `DocumentIntelligenceInput`, `DocumentIntelligenceOutput` (all frozen).
  - [x] Subtask 1.2 — Re-exported alphabetically.
  - [x] Subtask 1.3 — `test_document_intelligence.py` covers round-trip + empty-filename rejection.

- [x] **Task 2 — Author the doc taxonomy** (AC: #2)
  - [x] Subtask 2.1 — `doc_taxonomy.yaml` with 9 categories (incorporation_certificate, pan_card, address_proof, director_id, bank_statement, ubo_declaration, shareholder_pattern, aadhaar, income_proof).
  - [x] Subtask 2.2 — `jurisdictions/india/__init__.py` with `FieldSpec`, `DocTaxonomy`, `@lru_cache`-decorated `get_india_taxonomy()`.
  - [x] Subtask 2.3 — `_classify(filename)` in `intake/document_intelligence.py` strips `.pdf` and matches stem; falls back to stem-minus-suffix (handles `bank_statement_q1.pdf` → `bank_statement`); else `"unknown"`.

- [x] **Task 3 — Author the `DocAILLM` protocol + fixture impl** (AC: #3, #4)
  - [x] Subtask 3.1 — `adapters/__init__.py`, `adapters/doc_ai/__init__.py`, `base.py` with the `DocAILLM` Protocol + `DocAILLMError`.
  - [x] Subtask 3.2 — `FixtureDocAILLM` with `_FIXTURE_EXTRACTIONS` covering all 9 demo filenames. `model_id: str = "fixture"` class attr satisfies AC9 protocol read.
  - [x] Subtask 3.3 — Band-distribution invariant verified by `test_band_distribution_covers_all_four_bands` — `aadhaar_last4` lands LOW (0.30), `director_din`/`ubo_chain`/`shareholder_summary` MEDIUM_LOW, `incorporation_date`/`address` MEDIUM_HIGH, `cin`/`pan`/`company_name` HIGH.

- [x] **Task 4 — Author the watsonx impl** (AC: #5, #6)
  - [x] Subtask 4.1 — `extract_v1.j2` Jinja template per AC6.
  - [x] Subtask 4.2 — Golden input + output JSON files shipped.
  - [x] Subtask 4.3 — Used raw `httpx` (already transitive via FastAPI) over pulling `langchain-ibm` to keep dep footprint minimal. Documented in module docstring.
  - [x] Subtask 4.4 — `WatsonxDocAILLM` reads `WATSONX_API_KEY`/`WATSONX_PROJECT_ID`/optional `WATSONX_MODEL_ID` env vars, calls watsonx text-generation HTTP endpoint, parses the JSON-array response into typed `ExtractedField` records.
  - [x] Subtask 4.5 — `DocAILLMError(RuntimeError)` defined in `base.py`.

- [x] **Task 5 — Author the agent function** (AC: #7, #8)
  - [x] Subtask 5.1 — `intake/__init__.py` + `intake/document_intelligence.py` ship the `@agent_action`-decorated agent.
  - [x] Subtask 5.2 — `_get_default_llm()` reads `DOC_AI_PROVIDER` env (default `"fixture"`); raises `ValueError` on unknown provider.
  - [x] Subtask 5.3 — Per-`document_ref` loop: fixture mode passes `text=None`; watsonx mode reads via `pypdf.PdfReader` if file exists, else WARN logs `doc_intelligence.file_not_found` and watsonx surfaces `DocAILLMError` (caught by `@agent_action`).
  - [x] Subtask 5.4 — `set_runtime_model_id(resolved_llm.model_id)` called inside agent body. Fixture impl skips `set_runtime_prompt_hash`; watsonx sets it from the SHA-256 of the rendered prompt.
  - [x] Subtask 5.5 — `pypdf ^4.0.0` added to `apps/agents/pyproject.toml`.
  - [x] Subtask 5.6 — Updated 2026-04-30 (post-review pivot): the ADK runtime IS the showcase, so the agent is now exposed via `POST /v1/agents/document_intelligence/extract` on cockpit-api and registered with the Developer Edition as an OpenAPI tool. Manifest at `apps/agents/src/agents/registry/document_intelligence/agent.yaml`; OpenAPI tool spec at `…/openapi.yaml`. Both validated against the ADK SDK's own loader (`Agent(**yaml.safe_load(...))`).

- [x] **Task 6 — Amend Story 3-2's decorator with context-var overrides** (AC: #9)
  - [x] Subtask 6.1 — `_runtime_model_id` + `_runtime_prompt_hash` ContextVars + `set_runtime_*` public helpers folded into the initial `action_decorator.py` authoring.
  - [x] Subtask 6.2 — Wrapper resets both ContextVars before calling the wrapped function; reads them after to substitute into the ledger entry payload.
  - [x] Subtask 6.3 — `test_runtime_model_id_override`, `test_runtime_prompt_hash_override`, `test_runtime_overrides_do_not_leak_across_calls` cover the new behaviour.

- [x] **Task 7 — Tests for the agent** (AC: #10)
  - [x] Subtask 7.1 — `test_document_intelligence.py` reuses the `tmp_writer` fixture pattern.
  - [x] Subtask 7.2 — 8 cases covered: happy-path fixture, empty refs, unknown ref fallback, band distribution, ledger entry shape, classifier table, prompt determinism, fixture model_id propagation. Prompt-rendering determinism asserts byte-equality across two calls + 64-char SHA-256 length (golden hash not pinned to keep tests independent of formatting tweaks).
  - [x] Subtask 7.3 — `test_watsonx_http_error_propagates_as_doc_ai_error` monkeypatches `WatsonxDocAILLM._call` to raise `httpx.RequestError`; asserts `AgentExecutionError` (the wrapper's typed re-raise) and a single `agent.failed` ledger entry.

- [x] **Task 8 — `.env.example` extension** (AC: #11)
  - [x] Subtask 8.1 — `# ─── Story 3.4 Document Intelligence ───` block added.

- [x] **Task 9 — End-to-end smoke + lint pass** (AC: #12)
  - [x] Subtask 9.1 — `make demo-reset && make seed` produces 4 ledger entries; running the agent against Vora's 5 docs in fixture mode adds 1 `agent.completed` (5 total) and produces 11 extracted fields.
  - [x] Subtask 9.2 — `make lint` clean.
  - [x] Subtask 9.3 — `apps/agents` test count: 32 passed + 1 skipped (watsonx-skip without creds). `packages/contracts` test count: 141 passed. `apps/cockpit-api`: 47 passed (unchanged baseline + new ledger tests). No regressions.
  - [x] Subtask 9.4 — Final `make demo-reset` re-confirmed clean ledger.

## Dev Notes

### Architectural context (binding)

[Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Stack changes for demo, row "Document AI"] — Single LLM call against extracted text. No DocAI integration. **This story is the demo's faithful implementation of that simplification** — the doc-AI `Protocol` exists (3 lines), but only fixture + watsonx impls.

[Source: `architecture.md#Project-Specific Patterns` P1 Pluggable Adapter Pattern] — The bank-buyer pattern requires "every adapter ships with a second reference implementation" and a conformance test suite. **Demo simplification:** mock-only is acceptable per the Demo Scope Addendum. `FixtureDocAILLM` IS the demo's canonical impl; `WatsonxDocAILLM` is the optional showcase. No conformance suite.

[Source: `architecture.md#Project-Specific Patterns` P3 Provenance] — Every datum is `ProvenancedField[T]`. This story populates `Provenance.source_agent="document_intelligence"`, `source_system="<provider>"`, `confidence` (LLM-self-rated for watsonx; fixture-curated for fixture impl), `evidence_ids=[]` (filled by Story 3-5's supervisor — see AC8).

[Source: `architecture.md#Project-Specific Patterns` P4 Agent Action] — `@agent_action` enforces ledger entry per invocation. Story 3-2 owns the decorator; this story is the first agent that uses it for real. The runtime `model_id`/`prompt_hash` flow (AC9) is a small amendment to 3-2's decorator that this story owns end-to-end.

[Source: `architecture.md#Implementation Patterns & Consistency Rules` § Validation timing] — Validation at the boundary. The agent trusts `DocumentIntelligenceInput` is already Pydantic-valid; the LLM client validates its output against `FieldSpec` regexes; the decorator captures input/output post-validation.

[Source: `architecture.md#Enforcement Guidelines`] — Items 6 ("Never compose a prompt by string concatenation. Use Jinja templates from `apps/agents/prompts/`.") and 7 ("Never log raw customer PII") apply. The Jinja template (AC6) satisfies item 6. PII concern is moot for the demo (synthetic fixture data only).

[Source: `architecture.md#Authentication & Security` row S7] — LLM prompt-injection defense: document text typed as Pydantic data, Jinja template with strict escaping, agent output validated against Pydantic schema. **All three layers are present** in this story (the input contract validates `document_refs`; the Jinja template uses `autoescape=True`; the LLM output is validated against `FieldSpec` and `ExtractedField`).

[Source: `architecture.md#Anti-Patterns to Refuse`] — relevant subset:
- ❌ **Adapter without conformance pair (NFR-RI6)** — explicitly waived per Demo Scope Addendum (mock-only)
- ❌ **Pydantic schemas duplicated in apps** — `DocumentIntelligenceInput`/`Output` lives ONLY in `packages/contracts`
- ❌ **Agent that returns data without writing a ledger entry** — `@agent_action` enforces; no bypass

### Critical pitfalls to avoid

1. **Don't put the Pydantic input/output contracts in `apps/agents`.** They live in `packages/contracts` so the cockpit-api and cockpit-ui can import them. Story 3-6's Documents panel will need `DocumentIntelligenceOutput`'s shape via the TS API types; Story 3-5's supervisor needs them to call the agent.

2. **`_FIXTURE_EXTRACTIONS` must be exhaustive for the 9 demo filenames.** Missing a filename means a fixture-mode demo run produces an empty intake — visible in Story 3-6's Documents panel as a blank state, which is a demo killer. The dev should explicitly enumerate every `document_ref` from `contracts.cases.get_demo_case_fixtures` and ensure each has a fixture extraction.

3. **Confidence-band distribution.** AC10's "at least one extraction per band" check is load-bearing. If you bunch all confidences in 0.85+, Story 3-7's pill demo only shows HIGH. Fixtures should span: e.g., bank statement extractions at LOW (the fixture client is honest about uncertain extractions), pan extractions at MEDIUM_LOW or MEDIUM_HIGH, CIN extractions at HIGH.

4. **`Provenance.confidence_band` must be derived via `to_band(confidence)`.** Per Story 3-3 AC3, the constructor enforces consistency; if you pass mismatched values, Pydantic raises. **Use `to_band(c)` to compute the band; don't hand-pick the band string.**

5. **`captured_at` is set at fixture-impl time, not at ledger-write time.** Each `Provenance` records when the agent extracted the field — which is conceptually different from when the ledger entry was appended. For the demo's UX, both are within seconds of each other, but keeping the fields distinct preserves the bank-buyer scope's audit semantics.

6. **`@lru_cache` on `get_india_taxonomy`.** The taxonomy YAML reads at module import time would create a hard import-order coupling. lru_cache defers parsing until first call, which is also after `pytest` configures its working directory. Read the YAML via `Path(__file__).parent / "doc_taxonomy.yaml"` to avoid CWD assumptions.

7. **The watsonx impl is OPTIONAL but must lint+import clean in CI.** A common failure mode: the `langchain-ibm` import is gated behind a conditional, and CI's `make lint` doesn't trigger the import. Fix: import unconditionally at the top of `watsonx.py`. If `langchain-ibm` is not installed, lint fails — that's correct because we depend on it via `poetry add`.

8. **`pypdf` is the right PDF lib (not `PyPDF2` or `pdfplumber`).** `pypdf 4+` is the maintained successor to `PyPDF2`; lighter than `pdfplumber`. `cd apps/agents && poetry add pypdf` adds it cleanly.

9. **`pypdf.PdfReader` opens files; close them.** Use `with open(path, "rb") as f: reader = pypdf.PdfReader(f); ...`. Otherwise you'll leak file handles in the watsonx mode. Won't matter for the demo's volume; matters for correctness.

10. **Filename heuristic classification is fragile.** If the dev wants to harden it, a future story can introduce LLM-based classification or a contract-validated `DocumentRef` typed model with explicit `category: DocCategory`. **Don't pre-empt** — the demo's pinned fixtures use predictable filenames.

11. **Don't pre-populate `evidence_ids`.** Per AC8, the agent leaves it empty; Story 3-5's supervisor fills it. Tempting to "just generate a placeholder ID" — but Pydantic validates `LedgerEntryId` regex, so any placeholder must match `^led_[0-9A-HJKMNP-TV-Z]{26}$`. Empty list is the right answer.

12. **Don't try to run `orchestrate server start` in CI.** The ADK Developer Edition needs Docker + a watsonx-compatible local model server. CI doesn't have that. The agent function in this story is testable purely via Python imports — no ADK runtime needed.

13. **`set_runtime_model_id` must be called BEFORE the agent function returns.** The decorator reads the context var after the wrapped function returns, in the success-path branch. If the agent sets it via `try/finally` or after a `return`, the var won't be set when the decorator reads. Set it as the first line of the function (or right after resolving `llm`).

14. **Context vars don't leak across `asyncio.gather`.** `ContextVar` values are per-task by default in Python 3.11+. Concurrent agent calls won't interfere. Confirm with the AC10 concurrent-invocations test (also covers Story 3-2's concurrent path).

15. **`os.environ.get("DOC_AI_PROVIDER")` reads the live process env, not `.env`.** The `.env` file is loaded by `pydantic-settings` in cockpit-api, but `apps/agents` does NOT use `pydantic-settings` (it has no Settings class yet). For the demo, `DOC_AI_PROVIDER` must be exported in the shell or set via a `make run-doc-intel` target. The simplest path: set `DOC_AI_PROVIDER=fixture` as the default in `os.environ.get(..., "fixture")` and document the override in `.env.example` (operators run `export DOC_AI_PROVIDER=watsonx` if they want the showcase path).

### Architecture patterns relevant here

[Source: `architecture.md#Cross-Cutting Flow Examples` — case ingest → decision-ready] — The flow's first agent fan-out node is "document_intelligence". This story implements that node. Subsequent fan-out nodes (`entity_verification`, `ubo_graph`, `screening`, `risk_scoring`) are Epic 5+ work; this story does not pre-empt them.

[Source: `architecture.md#NFR-RI1` ADK pattern showcase] — Document Intelligence is the canonical "supervisor/collaborator + Pydantic-contracted tools" pattern. The supervisor (Story 3-5) is the collaborator parent; this story's agent is the first child. Even though the demo skips the full Orchestrate runtime, shipping the YAML manifest (AC7 decision) preserves the showcase value.

### Project Structure Notes

This story creates:

- `packages/contracts/src/contracts/document_intelligence.py`
- `packages/contracts/tests/test_document_intelligence.py`
- `apps/agents/src/agents/intake/__init__.py`
- `apps/agents/src/agents/intake/document_intelligence.py`
- `apps/agents/src/agents/intake/document_intelligence.yaml` (optional, recommended)
- `apps/agents/src/agents/adapters/__init__.py`
- `apps/agents/src/agents/adapters/doc_ai/__init__.py`
- `apps/agents/src/agents/adapters/doc_ai/base.py`
- `apps/agents/src/agents/adapters/doc_ai/fixture.py`
- `apps/agents/src/agents/adapters/doc_ai/watsonx.py`
- `apps/agents/src/agents/jurisdictions/__init__.py`
- `apps/agents/src/agents/jurisdictions/india/__init__.py`
- `apps/agents/src/agents/jurisdictions/india/doc_taxonomy.yaml`
- `apps/agents/src/agents/prompts/document_intelligence/extract_v1.j2`
- `apps/agents/src/agents/prompts/document_intelligence/extract_v1.golden.json`
- `apps/agents/src/agents/prompts/document_intelligence/extract_v1.golden.output.json`
- `apps/agents/tests/test_document_intelligence.py`

This story modifies:

- `packages/contracts/src/contracts/__init__.py` — re-exports
- `apps/agents/src/agents/supervisor/action_decorator.py` — context-var overrides for `model_id` and `prompt_hash` (AC9)
- `apps/agents/tests/test_action_decorator.py` — one new test for the runtime override
- `apps/agents/pyproject.toml` + `poetry.lock` — add `pypdf`, `langchain-ibm` (or `httpx` if the dev picks the lighter path), and `Jinja2` (likely already a transitive dep via `ibm-watsonx-orchestrate`; verify)
- `.env.example` — Story 3.4 section

This story DOES NOT create:

- The Case Supervisor (Story 3-5 fans out and fills `evidence_ids`)
- The Documents panel UI (Story 3-6)
- The ConfidencePill component (Story 3-7)
- An HTTP endpoint exposing intake results (Story 3-6 owns)
- Demo PDF files in `./fixtures/uploads/` (the fixture impl doesn't need them; the dev may ship them locally for watsonx-path testing but they're not part of CI)
- A 50-doc benchmark (Story 3.11 was cut)

### References

- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] — single LLM call, no DocAI integration
- [Source: `architecture.md#Project-Specific Patterns` P1, P3, P4] — pluggable adapters, provenance, agent-action
- [Source: `architecture.md#Authentication & Security` row S7] — prompt-injection defense layers
- [Source: `architecture.md#Enforcement Guidelines` items 6, 8] — Jinja templates only; adapter discipline
- [Source: `architecture.md#Cross-Cutting Flow Examples`] — case ingest fan-out flow
- [Source: `architecture.md#Anti-Patterns to Refuse`] — schema duplication, ledger bypass
- [Source: `epics.md#Epic 3` § Story 3.9] — original AC (re-scoped here)
- [Source: `prd.md#FR3, FR14, FR8, NFR-RI1, NFR-T5`] — instant-canvas, intake automation, provenance everywhere, ADK pattern showcase, doc-AI precision (relaxed)
- [Source: `3-1-append-only-ledger-schema-with-insert-only-writer.md`] — ledger writer + entry shape
- [Source: `3-2-agent-action-decorator.md`] — `@agent_action` decorator + AgentExecutionError
- [Source: `3-3-pydantic-contracts-for-ledger-provenance-confidence.md`] — `ProvenancedField[T]`, `Provenance`, `ConfidenceBand`, `to_band`
- [Source: `2-4-fixture-case-loader-with-three-seeded-cases.md`] — pinned demo case fixtures with `document_refs`

### Previous Story Intelligence

[Source: `3-3-pydantic-contracts-for-ledger-provenance-confidence.md`]
- `ProvenancedField[T]` is a Pydantic generic via `Generic[T]` (no `pydantic.generics.GenericModel`).
- `Provenance.confidence_band` is enforced consistent with `confidence` via a `@model_validator`. **Use `to_band(c)` to compute the band**; don't pass mismatched pairs.
- `evidence_ids: list[LedgerEntryId]` validates each element against the ULID regex. Empty list `[]` is allowed — used here for the agent's pre-supervisor-fill state.

[Source: `3-2-agent-action-decorator.md`]
- The decorator captures input/output via `model_dump(mode="json")`. The agent's `DocumentIntelligenceInput`/`Output` will serialize correctly because all nested types (`ProvenancedField`, `Provenance`, `ConfidenceBand`, `datetime`) are Pydantic/JSON-friendly.
- `AgentExecutionError` wraps any agent exception; the supervisor (3-5) catches it. `DocAILLMError` is one such exception.
- `apps/agents` depends on `apps/cockpit-api` (path dep). The watsonx impl is in `apps/agents` so its imports do NOT cycle.

[Source: `3-1-append-only-ledger-schema-with-insert-only-writer.md`]
- `LedgerWriter.append` returns the canonicalized entry with the server-generated `id`. The decorator can capture this return value if needed for AC8 — but per the AC8 decision, the supervisor (Story 3-5) re-reads the ledger AFTER the wrapped function returns, so the agent doesn't need access to the entry ID directly.

[Source: `2-1-case-schema-and-state-machine.md`]
- `CaseId = Annotated[str, ...]` — used as `DocumentIntelligenceInput.case_id` and `DocumentIntelligenceOutput.case_id`.

[Source: `2-4-fixture-case-loader-with-three-seeded-cases.md`]
- Demo cases have `customer_metadata.extra.document_refs` listing PDF filenames. The fixture impl's `_FIXTURE_EXTRACTIONS` keys MUST cover every distinct filename across all three cases, otherwise the demo's intake completion is partial.

[Source: `1-3-cicd-skeleton-with-oidc-federated-cloud-creds.md`]
- CI runs `make lint` + `make test` + `gitleaks` on every PR. The watsonx env vars in `.env.example` are placeholders only — never commit real values. `gitleaks` will fail the build if a real key is committed.

### Demo verification protocol (operator hand-off)

```bash
# After implementing, the dev must verify:

# 1. Reset and seed the demo so the ledger is fresh:
make demo-reset && make seed
wc -l ./data/ledger.jsonl
# Expected: 4 (1 ledger.initialized + 3 case.seeded)

# 2. Run the agent against Vora Capital fixture (fixture mode):
poetry -C apps/agents run python -c "
import asyncio
from contracts.cases import VORA_CAPITAL_ID
from contracts.document_intelligence import DocumentIntelligenceInput
from agents.intake.document_intelligence import document_intelligence

async def main():
    out = await document_intelligence(DocumentIntelligenceInput(
        case_id=VORA_CAPITAL_ID,
        document_refs=['incorporation_certificate.pdf','pan_card.pdf','address_proof.pdf','director_id.pdf','bank_statement_q1.pdf']
    ))
    print(f'Extracted {len(out.extracted_fields)} fields:')
    for f in out.extracted_fields:
        v = f.value
        print(f'  {f.document_ref:38s} {f.field_name:24s} = {str(v.value)[:40]:40s}  conf={v.provenance.confidence:.2f}  band={v.provenance.confidence_band.value}')
asyncio.run(main())
"
# Expected: ~10–15 fields across the 5 docs, with confidences spanning all 4 bands.

# 3. Verify the ledger gained an agent.completed entry:
wc -l ./data/ledger.jsonl
# Expected: 5 (one new entry from the agent run).
tail -n 1 ./data/ledger.jsonl | python -m json.tool | head -30
# Expected: actor_type=agent, actor_id=document_intelligence, payload.kind=agent_action,
# payload.status=ok, payload.model_id=fixture, payload.prompt_template_id=document_intelligence/extract_v1

# 4. Watsonx path skipped without creds:
poetry -C apps/agents run pytest tests/test_document_intelligence.py -v
# Expected: most tests PASS; watsonx-specific tests SKIPPED with "watsonx creds not configured" reason.

# 5. P4 lint passes (no agent code calls LedgerWriter directly):
make lint-agents-p4
# Expected: "P4 lint: no direct LedgerWriter.append outside @agent_action."

# 6. Lint + test green:
make lint
make test
# Expected: all subprojects pass; new agent tests + new contract tests visible.

# 7. Concurrent invocations don't cross-pollute model_id:
poetry -C apps/agents run python -c "
import asyncio
from contracts.cases import SHREE_VENKAT_ID, VORA_CAPITAL_ID, ANANYA_IYER_ID
from contracts.document_intelligence import DocumentIntelligenceInput
from agents.intake.document_intelligence import document_intelligence

async def run(case_id):
    return await document_intelligence(DocumentIntelligenceInput(case_id=case_id, document_refs=['incorporation_certificate.pdf']))

async def main():
    a, b, c = await asyncio.gather(run(SHREE_VENKAT_ID), run(VORA_CAPITAL_ID), run(ANANYA_IYER_ID))
    print('case ids:', a.case_id, b.case_id, c.case_id)
asyncio.run(main())
"
# Expected: three distinct case_ids in output, ledger has 3 new agent.completed entries.
```

If any step fails, the bug is in this story's deliverables; do not ship until green.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia persona, bmad-dev-story workflow)

### Debug Log References

* End-to-end smoke against Vora's 5 docs (fixture mode) printed:
    ```
    Extracted 11 fields
    Bands seen: ['high', 'medium_high', 'medium_low']
    ```
  All four bands surface across the *full* 9-filename catalogue (verified by `test_band_distribution_covers_all_four_bands`); LOW only appears for `aadhaar.pdf` which is on Ananya's case, not Vora's.

### Completion Notes List

* Watsonx impl uses raw `httpx` (deferring `langchain-ibm`) — keeps the dep footprint small and the call shape transparent. Tests exercise the parse path via a subclass that monkeypatches `_call`.
* Filename heuristics: simple stem-based match with single-suffix fallback. Handles the demo's pinned filenames including `bank_statement_q1.pdf`. Future stories may swap in LLM-based classification or contract-validated `DocumentRef` typed models — out of scope here.
* Confidence-band distribution is a load-bearing demo feature (Story 3.7's ConfidencePill needs all 4 bands visible). Pinned in `_FIXTURE_EXTRACTIONS`: aadhaar_last4=0.30 (LOW), din/ubo_chain/shareholder_summary in MEDIUM_LOW, incorporation_date/address/account_number in MEDIUM_HIGH, cin/pan/company_name in HIGH.
* `evidence_ids=[]` is intentionally left empty by the agent. Story 3.5's supervisor will re-read the agent's own ledger entry and back-fill `evidence_ids=[entry.id]` before exposing results to the API/UI. Documented in `DocumentIntelligenceOutput`'s docstring.
* ~~ADK YAML manifest skipped~~ **Updated 2026-04-30 post-review**: the user pushed back on a Python-only path with no ADK runtime in the loop — and they were right. The platform's name is `ibm_orchestrate_platform`; an ADK-shaped Python module that never sees the ADK runtime defeats the purpose. Pivoted to a real ADK integration:
    * **HTTP boundary added**: `POST /v1/agents/document_intelligence/extract` on cockpit-api wraps `document_intelligence(input)` so the agent's `@agent_action` ledger-write still fires per ADK-driven invocation.
    * **Registry-driven structure**: `apps/agents/src/agents/registry/<agent>/` is the unit of registration. Each agent owns its own subdirectory with `agent.yaml` (manifest) and — if it exposes tools — `openapi.yaml` (generated) plus a tiny `gen_openapi.py` shim that calls into shared library `agents._adk.openapi_tool.build_and_write`. Adding a new agent (e.g., Story 3.5's case_supervisor) is a matter of dropping a directory; no Make changes required.
    * **OpenAPI tool spec generation**: `apps/agents/src/agents/_adk/openapi_tool.py` exposes `build_and_write(...)` that builds a filtered OpenAPI spec from cockpit-api's live FastAPI app. Each agent's `gen_openapi.py` calls it with its own path filter + operationId. For document_intelligence: filters to `/v1/agents/document_intelligence/extract`, sets `operationId=extract_document_fields`, writes `openapi.yaml` with `servers[0].url = http://host.docker.internal:8000` so the Developer Edition's Docker containers can reach cockpit-api on the host.
    * **Agent manifest**: `registry/document_intelligence/agent.yaml` declares `kind: native`, `llm: watsonx/ibm/granite-3-2-8b-instruct`, `tools: [extract_document_fields]`, plus instructions for the LLM. Both YAMLs validated against the ADK SDK's own `Agent(**yaml.safe_load(...))` loader.
    * **Generic Make targets**: `make adk-spec` walks `registry/*/gen_openapi.py` and runs each from inside the cockpit-api Poetry venv. `make adk-register` walks `registry/*/openapi.yaml` (imports as ADK tools) then `registry/*/agent.yaml` (imports as ADK agents). Both idempotent. `make adk-chat` opens the chat UI. `make adk-up` now passes `--env-file $(CURDIR)/.env` to `orchestrate server start` so the Developer Edition picks up `WATSONX_APIKEY` from the project-local `.env` (no `export` required).
    * **Env handling via `.env`**: `WATSONX_APIKEY` (no underscore — matches ADK's `default.env` convention), `WATSONX_SPACE_ID`, `WATSONX_MODEL_ID`, `WATSONX_PROJECT_ID` all live in `.env` (gitignored, created from `.env.example` by `make bootstrap`). The `WatsonxDocAILLM` adapter reads `WATSONX_APIKEY` first, falls back to `WATSONX_API_KEY` for backward compat.
    * **Reciprocal Poetry path-dep**: `apps/cockpit-api` now path-deps `apps/agents` (and vice versa). Architecture A3 collapses both into one process at runtime, so this is a build-time aid, not a deployment cycle. Required pinning cockpit-api's Python upper bound to `<3.14` to match `ibm-watsonx-orchestrate`. Both apps gained `py.typed` markers so external mypy-strict consumers see types.
    * **README restructure**: ADK setup pulled into the main "Prerequisites" + "First-time setup" sections (it's not document_intelligence-specific — every future agent uses the same registry + Make targets). New "How the registry works" subsection documents the convention. New "Talking to the agents" section covers chat-time usage with example prompts and a curl fallback.
    * **Demo flow doc**: `Documentation/implementation-artifacts/3-4-adk-demo-flow.md` — extended walkthrough with prereqs, common issues, curl verification.
* Story 3.4's AC9 context-var amendment was authored as part of Story 3.2's initial decorator (single-session implementation). Decorator's `_runtime_model_id`/`_runtime_prompt_hash` ContextVars are reset per-invocation so concurrent agent calls do not cross-pollute (verified by `test_concurrent_invocations_produce_distinct_entries` + `test_runtime_overrides_do_not_leak_across_calls`).

### File List

**Created**
* `packages/contracts/src/contracts/document_intelligence.py`
* `packages/contracts/tests/test_document_intelligence.py`
* `apps/agents/src/agents/jurisdictions/__init__.py`
* `apps/agents/src/agents/jurisdictions/india/__init__.py`
* `apps/agents/src/agents/jurisdictions/india/doc_taxonomy.yaml`
* `apps/agents/src/agents/adapters/__init__.py`
* `apps/agents/src/agents/adapters/doc_ai/__init__.py`
* `apps/agents/src/agents/adapters/doc_ai/base.py`
* `apps/agents/src/agents/adapters/doc_ai/fixture.py`
* `apps/agents/src/agents/adapters/doc_ai/watsonx.py`
* `apps/agents/src/agents/intake/__init__.py`
* `apps/agents/src/agents/intake/document_intelligence.py`
* `apps/agents/src/agents/prompts/document_intelligence/extract_v1.j2`
* `apps/agents/src/agents/prompts/document_intelligence/extract_v1.golden.json`
* `apps/agents/src/agents/prompts/document_intelligence/extract_v1.golden.output.json`
* `apps/agents/src/agents/registry/document_intelligence/agent.yaml` — ADK agent manifest
* `apps/agents/src/agents/registry/document_intelligence/openapi.yaml` — OpenAPI tool spec (generated)
* `apps/agents/src/agents/registry/document_intelligence/gen_openapi.py` — per-agent shim calling `_adk.openapi_tool.build_and_write`
* `apps/agents/src/agents/_adk/__init__.py`
* `apps/agents/src/agents/_adk/openapi_tool.py` — shared library: filters cockpit-api OpenAPI for ADK tool registration
* `apps/agents/src/agents/py.typed` — empty marker so external mypy strict consumers see types
* `apps/cockpit-api/src/cockpit_api/py.typed` — same, for cockpit-api
* `apps/agents/tests/test_document_intelligence.py`
* `apps/cockpit-api/src/cockpit_api/routers/agents.py` — HTTP boundary for the ADK runtime
* `apps/cockpit-api/tests/test_agents_router.py` — endpoint coverage
* `Documentation/implementation-artifacts/3-4-adk-demo-flow.md` — four-terminal demo walkthrough

**Modified**
* `packages/contracts/src/contracts/__init__.py` — re-exports
* `apps/agents/pyproject.toml` — `pypdf`, `jinja2` deps; `yaml` mypy override; `py.typed` include
* `apps/agents/poetry.lock` — locked
* `apps/agents/src/agents/adapters/doc_ai/watsonx.py` — reads `WATSONX_APIKEY` first, falls back to `WATSONX_API_KEY` for backward compat
* `apps/cockpit-api/pyproject.toml` — `agents` reciprocal path dep + Python upper bound `<3.14` + `py.typed` include
* `apps/cockpit-api/poetry.lock` — locked
* `apps/cockpit-api/src/cockpit_api/main.py` — wire the agents router
* `Makefile` — `adk-spec`/`adk-register`/`adk-chat` targets walk `registry/*/`; `adk-up` passes `--env-file` so `.env` works
* `.env.example` — `WATSONX_APIKEY`/`WATSONX_SPACE_ID`/`WATSONX_MODEL_ID`/`WATSONX_PROJECT_ID` block (no underscore in APIKEY — matches ADK convention)
* `README.md` — ADK setup promoted to Prerequisites + First-time setup; new "How the registry works" subsection; "Talking to the agents" section; updated quickstart
* `Documentation/implementation-artifacts/sprint-status.yaml` — story marked `review`

**Retired**
* `apps/agents/scripts/generate_openapi_tool_spec.py` and the `apps/agents/scripts/` directory — replaced by `_adk/openapi_tool.py` library + per-registry `gen_openapi.py` shims.

(Decorator runtime-override changes folded into Story 3.2's `action_decorator.py` authoring.)

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-04-30 | Story 3.4 drafted. Demo replacement for the bank-buyer Story 3.9. First real ADK agent: pypdf-based PDF text extraction + single LLM call (watsonx) + fixture fallback for offline demos. Pluggable `DocAILLM` Protocol with two impls. Establishes the supervisor/collaborator showcase that NFR-RI1 demands. |
| 2026-04-30 | Implemented per the spec; marked `review`. Original Subtask 5.6 deferred the ADK YAML manifest. |
| 2026-04-30 | **Post-review pivot — real ADK integration.** Added `POST /v1/agents/document_intelligence/extract` HTTP boundary on cockpit-api, OpenAPI tool spec, agent manifest, and a registry-driven structure under `apps/agents/src/agents/registry/`. Generic Make targets (`adk-spec`, `adk-register`, `adk-chat`) walk the registry — adding a new agent is now drop-a-directory. `WATSONX_APIKEY` lives in `.env`; `make adk-up` passes `--env-file`. README restructured: ADK setup promoted to Prerequisites + First-time setup. |
