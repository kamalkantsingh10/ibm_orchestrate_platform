# Archived Story Files (2026-04-29 Demo Re-Scope)

These story files were authored under the original bank-buyer scope and were cut as part of the 2026-04-29 demo re-scope. They are preserved here (rather than deleted) because:

1. They contain detailed acceptance criteria that may be useful if the bank-buyer scope is ever revived
2. The work invested in writing them shouldn't vanish from the repository

**They are NOT part of the active demo build.** The active demo scope is defined by `../sprint-status.yaml`.

## Files in this archive

| File | Reason cut |
|---|---|
| `1-4-adr-discipline-and-architecture-documentation-skeleton.md` | ADR discipline optional for demo (NFR-RI2 deferred) |
| `1-5-postgres-tenant-schema-isolation-primitives.md` | Single-tenant SQLite for demo (no Postgres, no multi-tenant) |
| `1-6-oidc-authentication-with-cookie-session.md` | Replaced by user-switcher dropdown (3 hardcoded roles) |
| `1-7-deny-by-default-rbac-dependency.md` | Simplified to UI-side role gating |
| `1-8-tenant-scoping-middleware.md` | Single-tenant; no `tenant_id` enforcement |
| `1-9-session-inactivity-timeout.md` | N/A for single-user local demo |
| `1-10-empty-cockpit-shell-with-auth-protected-routes.md` | Replaced by `1-4-cockpit-shell-with-user-switcher-three-hardcoded-roles` (new) |
| `1-11-i18n-scaffolding-and-locale-aware-formatting.md` | Deferred — English-only for demo |

## Reference

- Sprint Change Proposal: `../../planning-artifacts/sprint-change-proposal-2026-04-29.md`
- PRD Demo Re-Scope Note: `../../planning-artifacts/prd.md` § "Demo Re-Scope Note (2026-04-29)"
- Architecture Demo Scope Addendum: `../../planning-artifacts/architecture.md` § "Demo Scope Addendum (2026-04-29)"
- Epics Demo Re-Scope: `../../planning-artifacts/epics.md` § "Demo Re-Scope (2026-04-29)"
