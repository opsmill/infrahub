# Quickstart: validating the community licensing contract

How to check that this feature works and that it changes nothing visible. Contracts: [license service](contracts/license-service.md), [info endpoint](contracts/api-info.md), [header](contracts/response-header.md), [telemetry](contracts/telemetry-license-block.md), [upgrade output](contracts/upgrade-output.md), [banner](contracts/frontend-banner.md).

## Prerequisites

- `uv sync --all-groups`, and the `python_sdk` submodule initialized and installed (`uv pip install -e python_sdk` in a fresh worktree).
- `cd frontend/app && pnpm install`.
- A running Docker daemon for component tests (`DOCKER_HOST` pointing at the user socket on macOS).

## 1. State rules and banner rules (seconds, no services)

```bash
uv run pytest backend/tests/unit/license -q
```

Expected: every state at every time boundary (one second before the start, the start, 30 days before the end, one second before the end, the end), for evaluation and commercial licenses, and every state × mode cell of the banner table pass.

## 2. Surfaces with a test license service

```bash
uv run pytest backend/tests/unit/api/test_internal_license.py backend/tests/unit/license/test_middleware.py -q
uv run pytest backend/tests/component/api/test_50_internals.py backend/tests/component/telemetry/test_tasks.py -q
```

Expected:

- `/api/info` returns the license object for each state; `/api/config` carries no license information;
- the header appears only in enforce mode, only on `/api` and `/graphql` paths;
- the stored telemetry snapshot carries the license block without the customer name, and `null` when no license is required.

## 3. Upgrade output

```bash
uv run pytest backend/tests/unit/license/test_reporting.py -q
```

Expected: the license section for each state matches [the contract](contracts/upgrade-output.md); nothing is printed for `not_required`.

## 4. Frontend

```bash
cd frontend/app && node_modules/.bin/vitest run src/entities/license src/entities/config
```

Expected: banner visibility per audience and role, dismissal per license and state, no banner when the license object is missing, and the About rows.

## 5. No visible change on Community

Run the local stack (`uv run invoke dev.start`), sign in as `admin`, and check:

- no banner on any page, and the About dialog has the same rows as before;
- `curl -si http://localhost:8000/api/schema/summary -H "X-INFRAHUB-KEY: ..." | grep -i x-infrahub-license` prints nothing;
- `docker exec <project>-server-1 infrahub upgrade --check` prints no license section, where `<project>` is the compose project `invoke dev.start` used (`INFRAHUB_BUILD_NAME`, by default the checkout directory's name without dashes);
- setting `INFRAHUB_LICENSE_KEY=anything` on the server and restarting logs one INFO line saying it is ignored, and nothing else changes.

## 6. Generated files and lint

```bash
uv run invoke schema.generate-jsonschema
cd frontend/app && pnpm codegen && cd -
uv run invoke docs.generate
uv run invoke format lint
```

Expected: `schema/openapi.json`, `types.generated.ts` and `docs/docs/reference/configuration.mdx` change only by the license additions, and lint is clean.
