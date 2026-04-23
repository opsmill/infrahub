# Quickstart — Schema Marketplace Integration

**Feature**: infp-528-schema-marketplace-page
**Audience**: Developers implementing or verifying this feature locally.

This walkthrough assumes a working Infrahub dev environment (backend, frontend, Neo4j, Prefect). If not set up, follow the repo's top-level `AGENTS.md` bootstrap first.

---

## 1. Configure the Marketplace URL

### Default (public Marketplace)

No config needed — `config.SETTINGS.marketplace.url` defaults to `https://marketplace.infrahub.app`.

### Override for testing (internal mirror, staging, fixture)

```shell
export INFRAHUB_MARKETPLACE_URL="https://marketplace-staging.example.com"
uv run invoke dev.start
```

The same `INFRAHUB_MARKETPLACE_URL` is read by `infrahubctl marketplace download` on the CLI side (SDK PR #952), so a single export reconfigures both. Misconfiguration (invalid scheme) logs a WARNING and `/api/marketplace/status` will report `url_scheme_valid: false`.

---

## 2. Smoke-test the proxy (no install)

With the backend running on `http://localhost:8000`:

```shell
# Auth: use an existing API token or the admin session cookie
export TOKEN="<your-api-token>"

# Health + config
curl -sH "X-INFRAHUB-KEY: $TOKEN" \
  http://localhost:8000/api/marketplace/status | jq

# List schemas
curl -sH "X-INFRAHUB-KEY: $TOKEN" \
  "http://localhost:8000/api/marketplace/schemas?limit=5" | jq '.items[].name'

# Schema detail
curl -sH "X-INFRAHUB-KEY: $TOKEN" \
  http://localhost:8000/api/marketplace/schemas/infrahub/vlan-translation | jq '.versions'

# Version content (raw YAML body wrapped in JSON)
curl -sH "X-INFRAHUB-KEY: $TOKEN" \
  "http://localhost:8000/api/marketplace/schemas/versions/<version_id>/content" | jq '.content'
```

Expected: all calls return 200 with populated bodies. No CORS errors in browser DevTools when using the frontend.

---

## 3. Install a schema via the UI (golden path)

**Preconditions**:
- You have at least one `CoreRepository` (writable) configured in Infrahub.
- Your user has write permission on that repository.

Steps:

1. Open `http://localhost:8000/` — confirm you land on the home page.
2. Verify the **Schema Marketplace tile** is visible:
   - If no user-defined schemas exist yet, the tile shows the onboarding CTA.
   - Otherwise, it renders in default state.
3. Click the tile — you should land on `/schema-marketplace`.
4. The page lists schemas fetched via `/api/marketplace/schemas`.
5. Pick a schema (e.g., `infrahub/vlan-translation`) → open the detail drawer.
6. Click **Install** → a repository picker shows only writable `CoreRepository` targets you have write access to.
7. Select a repository + branch → confirm.
8. The install drawer enters the `pending` state, then `running`, then `completed`. On completion, it links to the resulting commit.
9. Switch to your Git host — verify a new commit lands on the chosen branch under `schemas/…` with author metadata matching your Infrahub user.
10. Return to the home page — the tile no longer shows the onboarding CTA (unless your branch still has no user schemas for some reason).

---

## 4. Verify the CLI alternative (no-writable-repo path)

**Preconditions**:
- Either no repositories configured, OR only `CoreReadOnlyRepository` instances exist.

Steps:

1. Open `/schema-marketplace`.
2. Confirm the **prerequisite state** renders:
   - "All configured repositories are read-only" (if RO-only), or
   - "No Git repositories configured" (if none), with a link to repo creation.
3. Select one or more schemas.
4. Scroll to the **"Install via infrahubctl"** block. For each selected item, an `infrahubctl marketplace download …` line is shown; a single trailing `infrahubctl schema load ./schemas --branch <branch>` applies everything.
5. Click the copy button on the full block — paste into a shell:
   ```shell
   export INFRAHUB_ADDRESS=http://localhost:8000
   export INFRAHUB_API_TOKEN=<your-token>
   # Optional (only if your backend overrides the default Marketplace):
   # export INFRAHUB_MARKETPLACE_URL=https://marketplace-staging.example.com
   # paste the copied commands here — e.g.:
   infrahubctl marketplace download infrahub/vlan-translation -v 1.0.0
   infrahubctl schema load ./schemas --branch main
   ```
6. Verify the schema is applied to your Infrahub instance on the named branch (e.g., via GraphQL or `infrahubctl schema check`).

**Dependency**: the CLI alternative requires `opsmill/infrahub-sdk-python#952` (branch `knotty-dibble`) — the `python_sdk` submodule must be bumped to that commit (or post-merge) for `infrahubctl marketplace download` to be available.

---

## 5. Backend tests

```shell
# Unit tests (REST client + models)
uv run pytest backend/tests/unit/marketplace/ -v

# Functional tests (proxy endpoints, install workflow)
uv run pytest backend/tests/functional/marketplace/ -v

# Full integration (Docker): commits land in a real repo and repo-sync applies the schema
uv run invoke backend.test-integration -- -k marketplace
```

Each test module mirrors its production counterpart (`backend/infrahub/marketplace/`).

---

## 6. Frontend tests

```shell
cd frontend/app

# Unit tests (hooks + components)
pnpm test src/entities/schema-marketplace src/pages/schema-marketplace

# E2E — requires a running backend
pnpm test:e2e -- --grep "schema-marketplace"
```

Key Playwright scenarios (under `frontend/app/tests/e2e/schema-marketplace.spec.ts`):
- `home page shows the tile; no modal appears on refresh`
- `tile shows onboarding CTA when no user schemas exist`
- `schema library link in Getting Started widget routes to /schema-marketplace`
- `install golden path — pick repo, confirm, commit lands`
- `no-writable-repo state shows CLI alternative`
- `install drawer rejects read-only repo selection`

---

## 7. Lint, format, typecheck

```shell
uv run invoke format
uv run invoke lint           # ruff + mypy
cd frontend/app && pnpm biome:fix
cd frontend/app && pnpm typecheck
```

---

## 8. Regenerating generated files

After adding the new Pydantic models and routes:

```shell
uv run invoke backend.generate       # Updates backend/infrahub/core/protocols.py + schema/generated/
cd frontend/app && pnpm codegen      # Updates frontend/app/src/shared/api/rest/types.generated.ts
```

Commit the regenerated files alongside the hand-written changes. Do not hand-edit generated files (Principle I).

---

## 9. Rollback scenarios to verify manually

- Abort the Prefect flow mid-run (kill the worker after the schema is fetched but before `git push`) → verify the target repository is unchanged remotely.
- Set `INFRAHUB_MARKETPLACE_URL=not-a-url` → backend boots with a WARNING; `/api/marketplace/status` reports `url_scheme_valid: false`; frontend shows a config-error state on the Marketplace page.
- Block egress to `marketplace.infrahub.app` (e.g., `/etc/hosts` override) → `/api/marketplace/schemas` returns 502 within 10s; UI shows an error state within 10s (SC-004).
