# Quickstart / Validation: Frontend Request Prioritization (`X-Priority`)

**Feature**: IFC-2890 | **Date**: 2026-07-14

Runnable validation that the frontend emits `X-Priority` correctly on every transport, that the backend CORS preflight allows it, and that the interactive-vs-background scenario behaves. Implementation details live in `tasks.md`; this is a run/verify guide.

## Prerequisites

```bash
# Frontend deps
cd frontend/app && pnpm install

# Backend deps (for the CORS component test)
uv sync --all-groups
```

## 1. Frontend unit tests (per transport + opt-in)

Assert the **observable outbound header**, not injection internals (per the spec's testing decisions).

```bash
cd frontend/app
# The new priority module + all four transport tests
pnpm test src/shared/api/priority src/shared/api/graphql src/shared/api/rest
```

Expected — each transport test proves:

- **default `high`**: a request with no opt-in carries `X-Priority: high`.
- **opt-down `low`**: a request declared `low` carries `X-Priority: low`.
- **GraphQL replay**: an operation replayed after a simulated 401→refresh re-carries its `X-Priority`.
- **REST replay**: the stored-clone replay re-carries its `X-Priority`.
- **raw fetch external-host guard**: a `fetchUrl` to a non-Infrahub host carries **no** `X-Priority` (FR-007).
- **no `normal`**: no test path produces `normal` or an absent header on a frontend origin (FR-003).

## 2. Watched-status queries stay `high` (FR-005)

```bash
cd frontend/app
pnpm test src/entities/tasks src/entities/proposed-changes src/entities/branches -t "priority"
```

Expected: task list/status, proposed-change details/events, and branch action state polls emit `X-Priority: high`; none is declared `low`.

## 3. Backend CORS preflight (FR-006)

```bash
uv run invoke backend.test-unit -- -k "cors and priority"
# or the specific component test file added for this feature
```

Expected: an `OPTIONS` preflight with `Access-Control-Request-Headers: x-priority` returns a response whose `Access-Control-Allow-Headers` includes `x-priority`; a cross-origin request carrying the header is accepted. See [contracts/cors-preflight.contract.md](./contracts/cors-preflight.contract.md).

Manual check against a running server:

```bash
curl -i -X OPTIONS http://localhost:8000/api/... \
  -H 'Origin: http://localhost:5173' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: x-priority'
# → 200, and `access-control-allow-headers:` line contains x-priority
```

## 4. E2E interactive-vs-background scenario

```bash
cd frontend/app && pnpm test:e2e -g "x-priority|priority"
```

Expected: driving an interactive flow, all captured outbound requests carry `X-Priority: high`; a background-tagged flow carries `low`; none carries `normal`.

## 5. Adoption metric (SC-001, live check)

With a running stack, exercise representative UI flows, then:

```bash
curl -s http://localhost:8000/metrics | grep infrahub_admission_missing_priority_total
```

Expected: the counter stays at ~0 for frontend-origin traffic (frontend always sends an explicit `high`/`low`).

## Done when

- [ ] All four transports emit `X-Priority: high` by default and `low` when opted in.
- [ ] Header survives 401-refresh replay (GraphQL + REST) and file upload.
- [ ] No frontend-origin request emits `normal` or omits the header.
- [ ] External-host requests carry no `X-Priority`.
- [ ] CORS preflight allow-lists `x-priority`.
- [ ] Watched-status polls verified `high`.
