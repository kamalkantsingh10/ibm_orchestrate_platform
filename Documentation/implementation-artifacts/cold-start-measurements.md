# Cold-start measurements

Records of `make verify-timing` runs. Story 1.5 § AC #10 requires a fresh
clone reach the demo in ≤ 60 minutes. Use this log to spot regressions.

| Date | Machine | Bootstrap (s) | Migrate (s) | Seed (s) | Verify (s) | Total (s) | Notes |
|---|---|---:|---:|---:|---:|---:|---|
| 2026-04-29 02:48 UTC | Linux/x86_64 | 5 | 1 | 1 | 0 | 7 | bootstrap-only re-measurement (no clean); CI=0; verify=skipped |
| 2026-04-30 06:55 UTC | Linux/x86_64 | 5 | 1 | 1 | 0 | 7 | Story 2.4 — added 3 fixture cases to seed (sub-ms inserts; no measurable regression) |
