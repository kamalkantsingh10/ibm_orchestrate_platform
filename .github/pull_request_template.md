<!--
  Architecture review checklist below grows into reality as epics ship.
  Keep "N/A until Epic X" entries — reviewers tick what applies today.
-->

## Summary

<!-- One or two sentences: what changes and why. Link the story file. -->

## Changes

<!-- Bullet list of the substantive changes in this PR. -->

## Test plan

<!-- How a reviewer can verify locally. Include `make` targets used. -->

- [ ] `make lint` passes
- [ ] `make test` passes
- [ ] Manual verification steps:

## Architecture review checklist

Translated from `Documentation/planning-artifacts/architecture.md` →
"Enforcement Guidelines". Tick the items that apply to this PR; leave the
"N/A until Epic X" rows unchecked until that epic ships.

- [ ] No Pydantic schema duplicated across apps — shared models live in
      `packages/contracts/`.
- [ ] Every data-access function takes `tenant_id` as a keyword-only
      argument (architecture P2).
- [ ] No raw customer PII logged (logs hashed or omitted at the boundary).
- [ ] ADR added under `docs/adr/` if this PR makes a non-trivial design
      decision (NFR-RI2).
- [ ] Every agent invocation goes through `action_decorator` (P4) — _N/A
      until Epic 3._
- [ ] Every UI datum wraps in `ProvenancedField[T]` (P3) — _N/A until
      Epic 3._
- [ ] No prompt assembled by string concatenation (use Jinja templates) —
      _N/A until Epic 3._
- [ ] Adapter ships with conformance pair (NFR-RI6) — _N/A until Epic 3._
- [ ] No SSE payload > 256 bytes (P6) — _N/A until Epic 4._
