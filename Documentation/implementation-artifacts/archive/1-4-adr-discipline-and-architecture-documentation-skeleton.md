# Story 1.4: ADR discipline and architecture documentation skeleton

Status: ready-for-dev

## Story

As a future contributor evaluating the codebase,
I want every non-trivial design decision to live as a numbered ADR in `docs/adr/`,
So that decisions are traceable to rationale and the reference-implementation thesis (NFR-RI2) is honored.

## Acceptance Criteria

1. **AC1 — `docs/adr/` exists** with `0000-template.md` containing the canonical ADR structure: `Status` / `Context` / `Decision` / `Consequences`. Front-matter fields: `date`, `deciders`.
2. **AC2 — ADRs 0001–0008 are authored** capturing decisions already made in `architecture.md`:
   - `0001-monorepo-poetry-pnpm.md` — Polyglot monorepo, Poetry per Python project, pnpm for JS workspace, path-dep `packages/contracts/`.
   - `0002-postgres-over-db2.md` — PostgreSQL 16+ chosen over IBM Db2 for evaluator developer ergonomics (Path B); mature SQLAlchemy/asyncpg ergonomics; per-tenant schema isolation.
   - `0003-sse-over-websocket.md` — Server-Sent Events over WebSocket for real-time channel; one-way agent state, native `EventSource`, plays with cookie auth, auto-reconnect.
   - `0004-snake-case-json-wire-format.md` — `snake_case` JSON over the wire (not camelCase); Pydantic models source of truth, `openapi-typescript` preserves names, no humps/camelize translation layer.
   - `0005-vm-compose-over-k8s-mvp.md` — VM + Docker Compose for MVP; K8s-ready architecture but deferred; pilot SLO 99.5% achievable with restart-policies; "ship on a VM" reads better for Path B.
   - `0006-pluggable-adapter-pattern.md` — Adapter pattern (P1) for every external dep (DocumentStore, KeyVault, SecretsClient, Screening, DocAI); typed interface + reference impl + alternate impl + conformance suite.
   - `0007-shared-case-state-stateless-agents.md` — Resolution of agent memory model: shared `Case` Pydantic aggregate, agents are pure functions of `(case_state, input) → (output, ledger_entry)`; no per-agent episodic memory.
   - `0008-officer-app-managed-keypair.md` — App-managed Ed25519 keypair per officer (S6); generated at first login; private key encrypted at rest with tenant HSM master key; client signs in-browser via WebCrypto; server verifies. Avoids per-officer HSM provisioning.
3. **AC3 — Each ADR has Status: Accepted**, the date it was effectively decided (use `2026-04-27` — the architecture's effective date — for ADRs 0001–0008), at least one consequence (positive AND negative), and explicit cross-links to the source section in `architecture.md`.
4. **AC4 — `make adr-new title="my-decision"` creates a new sequentially numbered ADR** from the template. Sequence: scan `docs/adr/`, find max `NNNN`, increment, kebab-case the title, write the new file with frontmatter populated (status: Proposed, date: today, deciders: from `git config user.name`).
5. **AC5 — `docs/architecture/` exists** with the four document skeletons named in the architecture (none of these need to be deeply complete — skeletons + cross-links to `architecture.md` are sufficient at this stage):
   - `overview.md` — high-level architecture diagram + key flows; link out to `architecture.md`.
   - `data-flow.md` — case lifecycle, agent fan-out, ledger write; link to `architecture.md#Cross-Cutting Flow Examples`.
   - `tenant-isolation.md` — schema-per-tenant model, per-tenant signing keys, per-tenant VPC; link to `architecture.md#D2`, `S1`, `I9`, and Pattern P2.
   - `threat-model.md` — placeholder with required sections (assets, actors, threats, mitigations) and a banner: "Authoring scheduled for Story 11.1 (NFR-S4)". G1 from architecture is the explicit placeholder reason.
6. **AC6 — `docs/runbooks/` directory exists** with stubs for the runbooks named in the architecture's tree:
   - `tenant-onboarding.md` (NFR-SC4) — placeholder, full content lands later.
   - `tenant-offboarding.md` — placeholder.
   - `screening-vendor-swap.md` — placeholder + cross-link to Story 6.10 (procurement runbook).
   - `jurisdiction-pack-add.md` — placeholder.
   - `break-glass-access.md` (FR50, NFR-T6) — placeholder, full content lands Story 10.6.
   - `disaster-recovery.md` (NFR-A3) — placeholder, full content lands Story 11.3.
7. **AC7 — `docs/README.md` is the docs index**: links to ADRs (newest first), architecture sub-docs, and runbooks. Auto-generation script (`make docs-index`) is OPTIONAL — manual maintenance is acceptable while ADR count is < 20.
8. **AC8 — Every ADR is in committed Markdown** (no DOCX, no PDF, no Notion). ADRs are immutable once `Accepted` — superseding ADRs are NEW files (0009+) that link back to the older one's `Status: Superseded by 0NNN`.
9. **AC9 — A "How to write an ADR" mini-guide is in `docs/adr/README.md`** explaining: when to write one (any non-trivial decision per NFR-RI2), how to use the Make target, sequence-numbering rule, status lifecycle (Proposed → Accepted | Rejected → Superseded).

## Tasks / Subtasks

- [ ] **Task 1 — Create `docs/adr/` and the canonical template** (AC: #1, #9)
  - [ ] Subtask 1.1 — `mkdir -p docs/adr/`.
  - [ ] Subtask 1.2 — Author `docs/adr/0000-template.md`:
    ```markdown
    ---
    status: Proposed | Accepted | Rejected | Superseded by NNNN
    date: YYYY-MM-DD
    deciders: <names>
    ---

    # NNNN — Title in sentence case

    ## Context
    What is the issue we're seeing that motivates this decision?

    ## Decision
    What is the change we're proposing or doing?

    ## Consequences
    ### Positive
    -
    ### Negative
    -
    ### Neutral
    -

    ## References
    - [architecture.md#section](../planning-artifacts/architecture.md#section)
    ```
  - [ ] Subtask 1.3 — Author `docs/adr/README.md` mini-guide per AC9.

- [ ] **Task 2 — Author ADRs 0001–0008** (AC: #2, #3) — each ADR sourced from a specific architecture decision
  - [ ] Subtask 2.1 — `0001-monorepo-poetry-pnpm.md` — sources: `architecture.md#Repository Layout`, `#Workspace tooling`. Status: Accepted, date: 2026-04-27.
  - [ ] Subtask 2.2 — `0002-postgres-over-db2.md` — source: `architecture.md#D1`.
  - [ ] Subtask 2.3 — `0003-sse-over-websocket.md` — source: `architecture.md#A2`.
  - [ ] Subtask 2.4 — `0004-snake-case-json-wire-format.md` — source: `architecture.md#Naming Patterns` (Rationale callout).
  - [ ] Subtask 2.5 — `0005-vm-compose-over-k8s-mvp.md` — source: `architecture.md#I2`.
  - [ ] Subtask 2.6 — `0006-pluggable-adapter-pattern.md` — sources: `architecture.md#P1`, `#D5`, `#S1`, `#S2`, `#NFR-RI6`.
  - [ ] Subtask 2.7 — `0007-shared-case-state-stateless-agents.md` — source: `architecture.md#Resolution of Deferred Decisions` (agent memory model paragraph).
  - [ ] Subtask 2.8 — `0008-officer-app-managed-keypair.md` — source: `architecture.md#S6`, plus cross-link to `Pattern P5` (Officer Action Pattern).
  - [ ] Subtask 2.9 — Each ADR ≤ 1 page; cite exact section anchors in `Documentation/planning-artifacts/architecture.md`. Don't paraphrase architecture verbatim — extract the *decision* and *rationale* in 100–250 words; longer text stays in `architecture.md`.

- [ ] **Task 3 — Add `make adr-new` target** (AC: #4)
  - [ ] Subtask 3.1 — Append to root `Makefile`:
    ```
    adr-new:
    	@title="$(title)"; \
    	if [ -z "$$title" ]; then echo "Usage: make adr-new title=\"my-decision\""; exit 1; fi; \
    	next=$$(ls docs/adr/[0-9]*.md 2>/dev/null | sed 's:.*/\([0-9]*\)-.*:\1:' | sort -n | tail -1); \
    	next=$$(printf "%04d" $$((10#$${next:-0}+1))); \
    	slug=$$(echo "$$title" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9-'); \
    	file="docs/adr/$${next}-$${slug}.md"; \
    	cp docs/adr/0000-template.md "$$file"; \
    	sed -i "s/YYYY-MM-DD/$$(date +%Y-%m-%d)/" "$$file"; \
    	sed -i "s/NNNN — Title in sentence case/$${next} — $$title/" "$$file"; \
    	echo "Created $$file"
    ```
  - [ ] Subtask 3.2 — Verify: `make adr-new title="test sandbox decision"` creates `docs/adr/0009-test-sandbox-decision.md`. Delete the test file before committing.
  - [ ] Subtask 3.3 — Confirm gawk/sed/printf compatibility on macOS (BSD sed) AND Linux (GNU sed); use `sed -i.bak ... && rm *.bak` if needed for portability.

- [ ] **Task 4 — Author `docs/architecture/` skeletons** (AC: #5)
  - [ ] Subtask 4.1 — `docs/architecture/overview.md`: ~1 page summary, ASCII-diagram-or-link-to-mermaid, cross-links to `architecture.md` sections (`#Project Structure & Boundaries`, `#Cross-Cutting Flow Examples`).
  - [ ] Subtask 4.2 — `docs/architecture/data-flow.md`: brief recap of three flows from `architecture.md#Cross-Cutting Flow Examples` (case ingest, officer commit, vendor swap). Mermaid diagrams optional; if used, render-tested in a Markdown previewer.
  - [ ] Subtask 4.3 — `docs/architecture/tenant-isolation.md`: tenant scoping at code (`tenant_id` keyword arg per P2), data (schema-per-tenant per D2), key (per-tenant HPCS per S1), infra (per-tenant VPC per I9), observability (per-tenant namespace per NFR-O4) — one paragraph each, with anchor links.
  - [ ] Subtask 4.4 — `docs/architecture/threat-model.md`: placeholder with banner "Full threat model authored in Story 11.1 (NFR-S4)". Required section stubs: Assets, Actors, Threats (STRIDE breakdown), Mitigations.

- [ ] **Task 5 — Author `docs/runbooks/` stubs** (AC: #6)
  - [ ] Subtask 5.1 — Each stub: 1-line description + "Full runbook authored in Story X.Y" pointer. Files:
    - `tenant-onboarding.md` (placeholder; pointer not yet assigned — flag in story for backlog)
    - `tenant-offboarding.md` (placeholder)
    - `screening-vendor-swap.md` → Story 6.10
    - `jurisdiction-pack-add.md` (placeholder; flag for backlog)
    - `break-glass-access.md` → Story 10.6
    - `disaster-recovery.md` → Story 11.3

- [ ] **Task 6 — Author `docs/README.md`** (AC: #7)
  - [ ] Subtask 6.1 — Sections: ADRs, Architecture sub-docs, Runbooks. Each section is a Markdown list; ADR list has newest-first ordering with title and one-line summary.

- [ ] **Task 7 — Tests**
  - [ ] Subtask 7.1 — `make adr-new title="probe"` creates `docs/adr/0009-probe.md`; verify content matches template; delete file.
  - [ ] Subtask 7.2 — Markdown lint (e.g., `markdownlint-cli2`) on `docs/**/*.md` exits 0 — run via `make lint` if cheap to add; otherwise document as future work.
  - [ ] Subtask 7.3 — Manual review: each ADR (0001–0008) compiles in a Markdown previewer; cross-links resolve.
  - [ ] Subtask 7.4 — `gitleaks` doesn't flag any ADR (sanity — ADRs may quote example tokens).

## Dev Notes

### Architectural context

[Source: prd.md#NFR-RI2] — "Every non-trivial design decision is captured in an ADR (architecture decision record)." This story is the foundation that subsequent stories add ADRs to. Every later story that introduces a non-trivial decision MUST add an ADR.

[Source: architecture.md#Implementation Patterns & Consistency Rules — Resolution of Deferred Decisions] — Three deferred decisions (screening vendor, doc AI stack, agent memory model) become ADRs WHEN the procurement / evaluation / implementation actually happens, not in this story. Story 1.4 captures the eight currently-decided architecture decisions (D1, D2, A2, naming convention, I2, P1+ family, agent memory model resolution, S6).

[Source: architecture.md#Gap Analysis Results — G1] — Threat model is referenced as `docs/architecture/threat-model.md` but not yet authored. NFR-S4 mandates it. **This story authors the placeholder; Story 11.1 authors the full threat model.**

### ADR style discipline

ADRs are short. Architecture.md is the long-form reference; ADRs distill the single decision and its rationale.

**Good ADR**: 100–300 words. Decision is a single sentence. Context explains the constraint. Consequences include both positive AND negative.

**Bad ADR**: re-pasting an entire architecture section. Bullet-list-of-tradeoffs without a Decision sentence. Missing Consequences (especially the negative ones).

[Source: architecture.md#Decision Impact Analysis] — Each architecture decision lists "cascading implications" — those become the Consequences in the corresponding ADR. Mine that section for content.

### Why ADRs 0001–0008 in this specific order

Architecture decisions are categorized D/S/A/F/I (Data, Security, API, Frontend, Infra) plus 8 patterns (P1–P8). The eight ADRs map roughly to the **most cross-cutting + most-likely-to-be-questioned** decisions:

1. **Monorepo + Poetry/pnpm** — first thing every contributor sees.
2. **Postgres over Db2** — surprising for IBM-heavy stack; deserves justification (Path B evaluator ergonomics).
3. **SSE over WebSocket** — boring 2026 pick but actively questioned in 2026 by people defaulting to WebSocket.
4. **snake_case JSON wire format** — strong opinion against the JS-world default; deserves explicit rationale.
5. **VM + Compose over K8s** — counterintuitive at MVP scale; "ship on a VM" is the anti-K8s case.
6. **Pluggable Adapter Pattern** — the P1 architectural principle; touches every external dep.
7. **Shared case state + stateless agents** — resolution of a deferred decision (agent memory).
8. **Officer-managed Ed25519 keypair** — Path B win, novel; deserves detail.

Other decisions (S1 HPCS / Vault Transit, S5 hand-rolled RBAC, F1 TanStack Query, F3 TanStack Router, F5 Tiptap, etc.) are **NOT** in this batch — they get ADRs as their respective stories ship (e.g., S1 ADR is owned by Story 3.2 / 3.3; S5 by Story 1.7).

### Critical pitfalls to avoid

1. **Don't write ADRs that paraphrase architecture.md** — that's documentation duplication, the kind that rots. The ADR is the **decision**; the architecture is the **integrated picture**. Cross-link aggressively.
2. **Status: Accepted is permanent.** If the decision needs to change, write a NEW ADR (e.g., `0042-postgres-to-cockroachdb.md`) that supersedes; mark the old one `Status: Superseded by 0042`. Never edit an Accepted ADR.
3. **No emoji or marketing voice in ADRs.** Plain technical English. Voice = "we decided X because Y; the cost is Z."
4. **`make adr-new` portability**: macOS BSD sed and Linux GNU sed differ on `-i`. Either use `sed -i ''` (macOS) and `sed -i` (Linux) split, or use a portable alternative (Python script). Test on both platforms before claiming AC4.
5. **Threat model placeholder must NOT mislead** readers into thinking it's complete. Big banner: "Placeholder — full content authored in Story 11.1 (NFR-S4)".
6. **Don't cluster all consequences under "Positive"** — every architecture decision has tradeoffs; state them honestly. If you can't state a negative, you don't yet understand the decision.

### Project Structure Notes

Creates:
- `docs/adr/0000-template.md`
- `docs/adr/README.md`
- `docs/adr/0001-monorepo-poetry-pnpm.md`
- `docs/adr/0002-postgres-over-db2.md`
- `docs/adr/0003-sse-over-websocket.md`
- `docs/adr/0004-snake-case-json-wire-format.md`
- `docs/adr/0005-vm-compose-over-k8s-mvp.md`
- `docs/adr/0006-pluggable-adapter-pattern.md`
- `docs/adr/0007-shared-case-state-stateless-agents.md`
- `docs/adr/0008-officer-app-managed-keypair.md`
- `docs/architecture/overview.md`
- `docs/architecture/data-flow.md`
- `docs/architecture/tenant-isolation.md`
- `docs/architecture/threat-model.md` (placeholder)
- `docs/runbooks/*.md` (six placeholders)
- `docs/README.md` (index)

Modifies:
- Root `Makefile` (adds `adr-new` target).

The existing `docs/` folder is empty; this story populates it.

### References

- [Source: architecture.md#Implementation Handoff] — "supplemental ADRs in `docs/adr/` for deltas."
- [Source: architecture.md#Decision Priority Analysis] — Critical/Important/Routine decision categorization.
- [Source: architecture.md#Resolution of Deferred Decisions] — agent memory model resolution sourced for ADR 0007.
- [Source: architecture.md#Gap Analysis Results — G1] — threat model placeholder rationale.
- [Source: prd.md#NFR-RI2] — ADR discipline.
- [Source: epics.md#Story 1.4: ADR discipline and architecture documentation skeleton]

### Previous Story Intelligence

[Source: 1-1-bootstrap-the-polyglot-monorepo-from-the-canonical-scaffold.md]
- The repo's top-level `docs/` folder exists and is empty. This story populates it.
- ADR-relevant naming convention: `docs/adr/NNNN-<kebab-title>.md` (architecture.md#Structural Patterns).
- Architecture pinned: stack versions, conventions, patterns. Each ADR cross-references the relevant architecture section.

[Source: 1-2-one-command-local-development-environment.md]
- Root `Makefile` exists with bootstrap/dev/lint/test targets. This story APPENDS `adr-new`; it does not replace the file.
- Pre-commit hook `markdownlint` is candidate for `make lint` (only if cheap to add).

[Source: 1-3-cicd-skeleton-with-oidc-federated-cloud-creds.md]
- `.github/pull_request_template.md` references the architecture review checklist. **Add a checklist item**: "If this PR introduces a non-trivial design decision, an ADR is added in `docs/adr/`." (This may need to be added to that template separately or as a follow-up edit — flag it.)

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
