# Story 1.11: i18n scaffolding and locale-aware formatting

Status: ready-for-dev

## Story

As a future operator who needs to deploy in non-English markets,
I want the cockpit's strings externalized and `Intl.*` formatting in place from day one,
So that adding Hindi or any regional language post-MVP is a translation task (NFR-AC6, UX-DR38).

## Acceptance Criteria

1. **AC1 — `react-i18next` is wired in cockpit-ui** with the i18next core + browser language detector + http backend (for future remote catalogs; MVP serves bundled JSON locally). Initialized in `apps/cockpit-ui/src/lib/i18n.ts` (replacing the placeholder passthrough from Story 1.10). `<I18nextProvider>` is mounted in `main.tsx`.
2. **AC2 — English (`en`) catalog exists** at `apps/cockpit-ui/src/locales/en/common.json`. Every visible string in cockpit-ui is keyed via `useTranslation` / `t('key')` — no hardcoded user-facing literals in JSX (lint-enforced per AC4).
3. **AC3 — `Intl.*` formatters are exposed via `lib/format.ts`**:
   - `formatDate(d: Date | string, opts?: Intl.DateTimeFormatOptions)` — uses `Intl.DateTimeFormat` with the active locale; default ISO 8601 (`YYYY-MM-DD HH:mm`) per UX-numerical formatting.
   - `formatNumber(n: number, opts?)` — `Intl.NumberFormat` with the active locale.
   - `formatCurrency(amount: string | number, currency: string, opts?)` — `Intl.NumberFormat` with `style: 'currency'`. **Indian currency** uses `en-IN` lakh/crore convention (UX-numerical formatting: `₹1,25,000 · ₹50L · ₹2.5Cr`). For MVP, the canonical Indian abbreviation pattern (`1.25L`, `2.5Cr`) is implemented as a custom formatter on top of `Intl` since `Intl` does not natively emit Indian abbreviations.
   - `formatPercent(n: number, opts?)` — integer unless `< 10%`, then 1 decimal (UX rule).
   - `formatDuration(seconds: number)` — short form (`9m`, `1h 24m`) per UX rule.
4. **AC4 — Custom ESLint rule `cockpit-i18n-no-hardcoded-strings`** flags string literals appearing in JSX text content or as the value of `aria-label`/`alt`/`title`/`placeholder` props. Allow-list: technical strings (`"button"`, `"submit"`), test files, story files, locale files. Implementation can be a project-local ESLint plugin (`tools/eslint-plugin-cockpit/`) or simpler: `eslint-plugin-i18next/no-literal-string` configured against the project.
5. **AC5 — Story 1.10's placeholder `t()` is removed**; all strings flow through `react-i18next`. Keys defined in `en/common.json` (additions to seed):
   ```json
   {
     "cockpit": {
       "queue": { "empty": "No cases in queue · you're caught up", "count": "Queue · {{count}} cases" },
       "canvas": { "empty": "No case selected · pick one from the queue" },
       "decision": { "placeholder": "No decision pending" },
       "ribbon": { "all_quiet": "All systems quiet" },
       "topbar": { "signout": "Sign out", "notifications": "Notifications" },
       "session": { "expired_toast": "Your session expired — please sign in again" }
     },
     "common": {
       "yes": "Yes",
       "no": "No",
       "cancel": "Cancel",
       "submit": "Submit"
     }
   }
   ```
6. **AC6 — RTL-readiness**: layout uses CSS logical properties (`margin-inline-start`, `padding-block`, `text-align: start`) instead of `left`/`right` where it doesn't constrain layout. Tailwind 4 has `ms-*`/`me-*` utilities — use them. Document the choice in `tokens.css` comments.
7. **AC7 — Font stack covers Indian scripts**: Inter Variable handles Latin; for future Devanagari / Tamil / Telugu / Bengali, the `--font-sans` stack includes `'Noto Sans'` as a fallback (UX-spec promise). For MVP, only Inter is loaded; Noto Sans is referenced in the stack but NOT pre-loaded (saves bandwidth).
8. **AC8 — `formatCurrency('1500000', 'INR')` returns `₹15,00,000`** (Indian numbering — lakh grouping); abbreviation form returns `₹15L`. Tests cover both representations and the threshold rules:
   - amounts < 1L → grouped Indian numbering, no abbreviation.
   - 1L ≤ amount < 1Cr → `<n.n>L`.
   - amount ≥ 1Cr → `<n.n>Cr`.
9. **AC9 — Locale switching is wired** but the locale picker UI is NOT in MVP — locale defaults to `en-IN` (Indian English: ISO date format, Indian numbering). A `?lang=` query param OR a runtime call to `i18n.changeLanguage('en-US')` can switch. Document in README.
10. **AC10 — Tests cover**:
    - Render any cockpit component → `t('cockpit.queue.empty')` resolves to "No cases in queue · you're caught up".
    - `formatCurrency('1500000', 'INR')` → `₹15,00,000`.
    - `formatCurrency('1500000', 'INR', { abbreviated: true })` → `₹15L`.
    - `formatDate(new Date('2026-04-27T14:32Z'))` with `en-IN` → `"2026-04-27 · 14:32 IST"` (or equivalent — verify UX format).
    - ESLint rule fires on `<button>Submit</button>` literal; silent on `<button>{t('common.submit')}</button>`.

## Tasks / Subtasks

- [ ] **Task 1 — Install + wire `react-i18next`** (AC: #1, #5, #9)
  - [ ] Subtask 1.1 — `cd apps/cockpit-ui && pnpm add i18next react-i18next i18next-browser-languagedetector i18next-http-backend`.
  - [ ] Subtask 1.2 — `apps/cockpit-ui/src/lib/i18n.ts`:
    ```ts
    import i18n from 'i18next';
    import { initReactI18next } from 'react-i18next';
    import LanguageDetector from 'i18next-browser-languagedetector';
    import HttpBackend from 'i18next-http-backend';
    import enCommon from '../locales/en/common.json';

    void i18n
      .use(HttpBackend)
      .use(LanguageDetector)
      .use(initReactI18next)
      .init({
        fallbackLng: 'en-IN',
        supportedLngs: ['en-IN', 'en-US'],
        defaultNS: 'common',
        ns: ['common'],
        resources: { 'en-IN': { common: enCommon }, 'en-US': { common: enCommon } },
        interpolation: { escapeValue: false },
        detection: { order: ['querystring', 'localStorage', 'navigator'], caches: ['localStorage'] },
      });

    export default i18n;
    ```
  - [ ] Subtask 1.3 — `apps/cockpit-ui/src/main.tsx`: import `./lib/i18n` (side-effect init).
  - [ ] Subtask 1.4 — Replace Story 1.10's placeholder `t()` everywhere — switch to `useTranslation()` hook.

- [ ] **Task 2 — Author `en/common.json`** (AC: #2, #5)
  - [ ] Subtask 2.1 — Seed with the keys named in AC5. Group by feature area.
  - [ ] Subtask 2.2 — Add a CI lint that flags missing keys: any `t('foo.bar')` call whose key is not present in the catalog → fail. Tooling: `i18next-parser` extracts keys; diff against catalog.
  - [ ] Subtask 2.3 — Document in README: "Adding a string → add the key to `en/common.json`; lint will fail otherwise."

- [ ] **Task 3 — Author `lib/format.ts`** (AC: #3, #8)
  - [ ] Subtask 3.1 — `formatDate(d, opts)` — default to `en-IN` locale, ISO date + 24h time.
  - [ ] Subtask 3.2 — `formatNumber(n, opts)`.
  - [ ] Subtask 3.3 — `formatCurrency(amount, currency, opts)`:
    ```ts
    export function formatCurrency(
      amount: string | number,
      currency: string,
      opts: { abbreviated?: boolean; locale?: string } = {},
    ): string {
      const locale = opts.locale ?? i18n.language;
      const num = typeof amount === 'string' ? Number(amount) : amount;
      if (currency === 'INR' && opts.abbreviated) {
        if (num >= 1e7) return `₹${(num / 1e7).toFixed(num % 1e7 === 0 ? 0 : 1)}Cr`;
        if (num >= 1e5) return `₹${(num / 1e5).toFixed(num % 1e5 === 0 ? 0 : 1)}L`;
      }
      return new Intl.NumberFormat(locale, {
        style: 'currency',
        currency,
        maximumFractionDigits: currency === 'INR' ? 0 : 2,
      }).format(num);
    }
    ```
  - [ ] Subtask 3.4 — `formatPercent(n)`: integer if ≥ 10, else 1 decimal.
  - [ ] Subtask 3.5 — `formatDuration(seconds)`: `9m`, `1h 24m`, `2d 3h`.

- [ ] **Task 4 — Custom ESLint rule** (AC: #4)
  - [ ] Subtask 4.1 — Investigate `eslint-plugin-i18next` (or `eslint-plugin-react-i18n`). If it covers our needs, install + configure. If not, author a small project-local plugin in `tools/eslint-plugin-cockpit/`.
  - [ ] Subtask 4.2 — Configure rule:
    - Allow string literals as JSX prop *names*.
    - Allow string literals as `className`/`data-*`/`aria-*` attribute keys.
    - Disallow string literals as JSX text children, `aria-label`/`alt`/`title`/`placeholder` values UNLESS already wrapped in `t(...)`.
    - Allowlist common technical strings (`""`, single chars, technical prop values).
    - Allowlist `*.test.{ts,tsx}` and `*.stories.{ts,tsx}`.
  - [ ] Subtask 4.3 — Add to `apps/cockpit-ui/eslint.config.js` (or `.eslintrc.cjs`). Verify `pnpm lint` flags `<button>Submit</button>` and is silent on `<button>{t('common.submit')}</button>`.

- [ ] **Task 5 — RTL + logical properties** (AC: #6, #7)
  - [ ] Subtask 5.1 — Audit `apps/cockpit-ui/src/components/cockpit/**/*.tsx` for `left-*`/`right-*`/`pl-*`/`pr-*` Tailwind utilities. Replace with `start-*`/`end-*`/`ps-*`/`pe-*`.
  - [ ] Subtask 5.2 — Update `--font-sans` in `tokens.css`:
    ```css
    --font-sans: 'Inter', 'Noto Sans', system-ui, sans-serif;
    ```
  - [ ] Subtask 5.3 — Document RTL approach in `docs/architecture/overview.md` (Story 1.4 placeholder) — short paragraph; full RTL polish is post-MVP.

- [ ] **Task 6 — Tests** (AC: #10)
  - [ ] Subtask 6.1 — `apps/cockpit-ui/src/lib/format.test.ts`:
    - `formatCurrency('1500000', 'INR')` → matches `/₹15,00,000/`.
    - `formatCurrency('1500000', 'INR', { abbreviated: true })` → `₹15L`.
    - `formatCurrency('25000000', 'INR', { abbreviated: true })` → `₹2.5Cr`.
    - `formatCurrency('99999', 'INR', { abbreviated: true })` → `₹99,999` (under threshold; no abbreviation).
    - `formatPercent(0.625)` → `62.5%`? Or is input expected as integer percent? **Decide & document**: input is fraction (0.625 → 62.5%). Update if UX expects integer-percent input.
    - `formatDuration(540)` → `9m`. `formatDuration(5040)` → `1h 24m`.
    - `formatDate(...)` with `en-IN` matches `/^\d{4}-\d{2}-\d{2} · \d{2}:\d{2} IST$/`.
  - [ ] Subtask 6.2 — `apps/cockpit-ui/src/components/cockpit/QueueRail/index.test.tsx` — assert empty state text is sourced from `t('cockpit.queue.empty')` (mock i18n with a fixture `t` that returns the key path; verify the path).
  - [ ] Subtask 6.3 — ESLint rule test (manual at first; consider an `eslint-rule-tester` for the custom rule).

## Dev Notes

### Architectural context

[Source: prd.md#NFR-AC6] — Localization: MVP ships English only; architecture supports i18n (externalized strings, locale-aware date/number formatting) from day one for future Hindi + regional Indian languages.

[Source: architecture.md#F9] — `react-i18next` with English-only catalog at MVP; locale-aware date/number via `Intl.*`. NFR-AC6 mandates externalized strings from day one.

[Source: ux-design-specification.md#Internationalization readiness] — All text externalized to message catalogs; type stack covers Indian scripts; no baked-in text direction; date/number/currency via `Intl.*` (not hand-rolled).

[Source: ux-design-specification.md#Numeric Formatting] — Indian numbering (lakh / crore): `₹1,25,000 · ₹50L · ₹2.5Cr`. Indian locale is the MVP default.

### Critical pitfalls to avoid

1. **`Intl.NumberFormat` with `en-IN` produces Indian numbering** (commas at lakh boundaries), but DOES NOT emit `L` or `Cr` abbreviations. Implement abbreviations as a custom layer on top — see Subtask 3.3.
2. **Don't load Noto Sans by default**. Add to font stack as fallback only; pre-load only Inter Variable. Pre-loading Noto Sans inflates first-paint without user benefit in English-only MVP.
3. **`i18n.changeLanguage` triggers a re-render** of every component using `useTranslation`. Ensure no hooks depend on the locale changing mid-flow without re-render coverage.
4. **The custom ESLint rule's allowlist must include**: shadcn/ui copies (`apps/cockpit-ui/src/components/ui/*` — owned, but the strings inside are typically passed in by callers; check before flagging).
5. **Don't put `t()` calls in module scope**. They'll evaluate at module load time, before i18n is initialized. Always use `useTranslation()` inside components, or call `i18n.t()` at runtime within event handlers / effects.
6. **Pluralization**: `i18next` handles via `count` interpolation. Use `t('cockpit.queue.count', { count: cases.length })`. Plural rules vary by locale (Hindi has `one` and `other`; English has `one` and `other`). Don't hand-roll.
7. **Number of decimals**: UX rules say "Integer % unless < 10%, then 1 decimal." Code this exactly; don't generalize to "always 1 decimal" or you'll get `100.0%` everywhere.
8. **Currency formatter**: `Intl` requires a valid currency code. Pass through any received currency without validating against an allow-list — let bank cases denominated in EUR/USD work even though MVP is INR-default.
9. **Locale detection**: `i18next-browser-languagedetector` reads `navigator.language`, which on Indian users typically returns `en-IN` or `en-US`. Default `fallbackLng` to `en-IN` so Indian users hit the right number formatting on first render.
10. **Story 1.10's placeholder `t()` was a passthrough**. After this story, ALL `t('key')` calls expect the key to exist in `en/common.json`. Audit Story 1.10's components and add every key.

### Architecture patterns relevant here

[Source: architecture.md#Anti-Patterns to Refuse] — N/A directly, but the spirit: "no hand-rolled equivalent of `Intl.*`" is a quiet anti-pattern.

[Source: ux-design-specification.md#Implementation Guidelines (Internationalization)]
1. All user-facing strings pass through `t()` — no string literals in components.
2. Date / number / currency formatting uses `Intl.*` — never `.toLocaleString()` without explicit locale parameter.
3. Text direction honored — no `text-align: left` hardcoded; use `start` / `end` logical properties.
4. Font stack includes fallbacks for Indian scripts — Devanagari, Tamil, Telugu, Bengali glyphs covered by Inter + Noto Sans fallback.

### Project Structure Notes

Creates:
- `apps/cockpit-ui/src/lib/i18n.ts` (REPLACES Story 1.10's placeholder)
- `apps/cockpit-ui/src/lib/format.ts`
- `apps/cockpit-ui/src/lib/format.test.ts`
- `apps/cockpit-ui/src/locales/en/common.json`

Modifies:
- `apps/cockpit-ui/src/main.tsx` (mount i18n).
- All `apps/cockpit-ui/src/components/cockpit/**/*.tsx` from Story 1.10 — switch from placeholder `t()` to `useTranslation()`.
- `apps/cockpit-ui/eslint.config.js` (custom rule wiring).
- `apps/cockpit-ui/src/styles/tokens.css` (font-sans stack with Noto Sans fallback).
- `apps/cockpit-ui/package.json` (i18next deps).

### References

- [Source: prd.md#NFR-AC6]
- [Source: architecture.md#F9]
- [Source: ux-design-specification.md#Internationalization readiness]
- [Source: ux-design-specification.md#Numeric Formatting]
- [Source: ux-design-specification.md#Implementation Guidelines (Internationalization)]
- [Source: epics.md#Story 1.11: i18n scaffolding and locale-aware formatting]

### Previous Story Intelligence

[Source: 1-2-one-command-local-development-environment.md]
- ESLint with `--max-warnings=0` is the gate. The custom i18n-rule violations block merges.

[Source: 1-10-empty-cockpit-shell-with-auth-protected-routes.md]
- A placeholder `t()` was used: `const t = (_key: string, fallback: string) => fallback;`. **Replace** with `react-i18next`'s `useTranslation()`; every key referenced (e.g., `cockpit.queue.empty`, `cockpit.canvas.empty`, `cockpit.decision.placeholder`, `cockpit.signout`, `cockpit.crumbtrail.queue_count`, `cockpit.ribbon.all_quiet`, `cockpit.topbar.notifications`) must exist in `en/common.json`.
- Tailwind tokens already established in `tokens.css`. Font stack updated to include Noto Sans fallback.
- The `_auth.tsx` redirect-after-login flow uses localStorage `cockpit:returnTo` — i18n-relevant strings on the redirect targets need keys (`cockpit.session.expired_toast`).

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
