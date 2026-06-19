# Quickstart: verifying the custom prefix mask

Prereqs: dev stack running (deps in Docker, host API on :8000, Vite dev server on :8080). Log in (admin / infrahub). Demo dataset loaded.

> **As-built status**: Slice 1 (IP address) is accurate and was verified in the preview. **Slice 2 (IP prefix) is DEFERRED** — the control is hidden for prefix pools, so there is no prefix-length field to fill there. Range validation is **1–128** (the `33`-for-v4 check does not apply). Add this scenario instead: re-select an address pool that already holds a reservation for the object and enter a *different* length → inline error `its prefix length cannot be changed, only /<n> can be used` (FR-014); entering nothing reuses the reservation with no error. The Playwright specs below were **not** added; verification was manual.

## Manual verification (preview-driven)

### Slice 1 — IP address via relationship (frontend-only; verify first)

1. Open a device (Device Management → a device, e.g. `atl1-core1`) and click **Edit**.
2. On **Primary IP Address**, click the pool button and choose an address pool (e.g. *Loopbacks pool*).
3. Confirm the **Prefix length** control appears beneath the "Allocated by pool" chip, empty, with the pool default shown as placeholder/helper.
4. Enter a non-default length (e.g. `32`). Save.
5. Confirm the device's primary address was allocated at `/32` (open the allocated IP).
6. Repeat leaving the control empty → allocation uses the pool default (unchanged behaviour).

### Slice 2 — IP prefix / IP address via IPAM creation (needs backend change)

1. IPAM → create a prefix → set **Prefix** to *Allocated by pool*, pick a prefix pool.
2. Enter a length (e.g. `28`), save → confirm a `/28` is created.

### Negative / edge checks

- Enter `129` (or `33` for a v4 pool) → inline error, Save blocked.
- Enter a valid length the pool cannot satisfy → Save submits, backend allocation error shown inline, selection + entered length preserved (FR-013).
- Select a non-IP pool (e.g. a number pool field) → no prefix-length control.
- Change the selected pool after entering a length → length resets to empty.

## Automated

- Frontend unit (Vitest): gating, validation range, mutation-builder `prefixlen` emission.
- E2E (Playwright): extend `tests/e2e/ipam/ip-prefix-create-with-pool.spec.ts` and `ip-address-create-with-pool.spec.ts` to fill `pool-prefix-length-input` and assert the allocated mask.
- Backend: new tests asserting inline `from_pool` with `prefixlen` allocates at the requested length for address (exists) and prefix/attribute (after change), plus the unsatisfiable-length error path.

Run: `cd frontend/app && pnpm test` and `pnpm test:e2e`; backend `uv run invoke backend.test-unit` / functional tests. Run `/pre-ci` before pushing.
