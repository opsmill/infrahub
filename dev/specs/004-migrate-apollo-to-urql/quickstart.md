# Quickstart: Validating the Apollo → urql Migration

Runnable validation guide. Proves the transport swap preserves behavior (SC-002, SC-003, SC-004) and reduces bundle size (SC-001). Run from `frontend/app/`.

## Prerequisites

- `pnpm install` (with the updated dependency manifest: `@urql/core`, `@urql/exchange-auth` present; `@apollo/client`, `apollo-upload-client`, `@types/apollo-upload-client` removed).
- A running Infrahub backend for E2E / manual checks (see root `AGENTS.md`).

## 0. Bundle baseline (do this BEFORE the migration)

```bash
git switch develop && cd frontend/app && pnpm install && pnpm build
# Record the gzipped size of the main JS chunk(s) from the build output.
```
Then repeat on the feature branch after the swap and compare — expect a decrease (SC-001).

```bash
git switch migrate-apollo-to-urql-infp-563 && pnpm install && pnpm build
```

## 1. No stray Apollo references (SC-005)

```bash
grep -rn "@apollo/client\|apollo-upload-client" src   # expect: no matches
grep -n "apollo" package.json                          # expect: no matches
```

## 2. Static gates (SC-002)

```bash
pnpm exec biome ci .        # format + lint
pnpm knip                   # unused exports/files/deps (catches leftover apollo deps)
pnpm exec betterer ci       # TypeScript-regression gate
```

## 3. Unit + component tests (SC-002, SC-003)

```bash
pnpm test
```
Must include (see `contracts/transport-client.md` behavioral assertions):
- Rewritten transport tests: `X-Priority` default `high` / `low` override (assertion 1); `Authorization` present/absent (assertion 1).
- **FR-006 token refresh (SC-003)** — four cases: one refresh+replay succeeds; persistent `TOKEN_EXPIRED` after replay → redirect; refresh returns no token → redirect; refresh throws → redirect. No hung promise in any case.
- Result-shape: success → `errors === undefined`; partial-data-with-errors → both populated (assertions 3–4).

## 4. Dedup spike (Decision 3 — gating)

Before shipping, run the targeted check: fire two concurrent `graphqlClient.query` calls with identical document + variables but different `context.branch`, and assert each response reflects its own branch. If they collide, apply a mitigation from `research.md` Decision 3. Document the outcome.

## 5. Manual parity (SC-004)

Against a running backend, confirm indistinguishable behavior vs. the `develop` build:
- Authenticated browsing of objects (queries carry correct branch/time).
- Object create / update / delete (mutations).
- **File upload** on object create/update (multipart) — the two upload mutations succeed.
- **Token expiry recovery**: force an expired access token; confirm a single silent refresh + successful replay, and that an unrecoverable refresh bounces to `/login`.
- Branch-scoped views and a branch **diff/compare** view (exercises the cross-branch concurrency path from step 4).

## 6. E2E (SC-002, SC-004)

```bash
pnpm test:e2e
```
Existing Playwright suite must pass unchanged — it covers the user-facing flows; no new user-facing behavior is introduced by this migration.

## Done when

All of steps 1–6 pass, the dedup spike (step 4) is resolved or ruled out, and the bundle comparison (step 0) shows a decrease.
