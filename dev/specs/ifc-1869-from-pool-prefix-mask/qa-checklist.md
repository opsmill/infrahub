# QA Checklist — Custom prefix mask for from-pool allocation

**Generated**: 2026-07-21 12:17 CEST
**Feature**: dev/specs/ifc-1869-from-pool-prefix-mask
**Source**: speckit.opsmill.qa

## Scope

Verify that, when allocating an **IP address or IP prefix** from a resource pool in the UI, a
tester can optionally set a custom prefix length instead of the pool default — and that leaving
it empty preserves today's behaviour. In scope: the shared pool picker's prefix-length control on
IP **address** pools (`CoreIPAddressPool`) and IP **prefix** pools (`CoreIPPrefixPool`), its
validation (range `1–128`), gating, and the first-allocation conflict guard. Out of scope: number
pools, selecting the target object kind for generic IP relationships, and editing the mask of an
already-allocated address.

## Prerequisites

- [ ] Access to the preview environment: <https://infrahub-preview-9631.tailc018d.ts.net>
- [ ] Credentials to sign in (demo: `admin` / `infrahub`).
- [ ] Demo dataset present (a device such as `atl1-core1`, and an IP **address** pool such as *Loopbacks pool*).
- [ ] A modern browser; no local install needed for the preview path.
- [ ] (Local alternative only) Branch `from-pool-prefix-mask-infp-362` checked out with the demo stack running.

## Setup

Primary path — use the hosted preview (no local setup):

1. Open <https://infrahub-preview-9631.tailc018d.ts.net/objects/InfraDevice>
2. Sign in (`admin` / `infrahub`).
3. Confirm the device list loads and at least one IP address pool exists (Objects → Resource Manager).

Local alternative (only if not using the preview):

```bash
uv run invoke demo.start
uv run invoke demo.load-infra-schema
uv run invoke demo.load-infra-data
# UI at http://localhost:8000
```

## Test Scenarios

### 1. Allocate an IP address at a custom prefix length

**What this verifies**: A user can allocate from a pool at a non-default mask in one form interaction (US1 / SC-001).

**Steps**:

- [ ] Open a device (Device Management → e.g. `atl1-core1`) and click **Edit**.
- [ ] On **Primary IP Address**, click the pool button and choose an IP address pool (e.g. *Loopbacks pool*).
- [ ] Confirm a **Prefix length · optional** control appears beneath the "Allocated by pool" chip, empty, with the pool default shown as the placeholder.
- [ ] Enter a length that differs from the placeholder default (example: `32`), then **Save**.
- [ ] Open the newly allocated address from the device.

**Expected result**: The primary address is created at the length you entered (e.g. `/32`), not the pool default.

### 2. Leave it empty → pool default (zero-effort path)

**What this verifies**: The existing one-step flow is unchanged when the control is left untouched (US2 / SC-002, SC-005).

**Steps**:

- [ ] On a device Edit form, set **Primary IP Address** to allocate from the same address pool.
- [ ] Read the placeholder — it communicates the pool's default prefix length.
- [ ] Leave the **Prefix length** control empty and **Save**.
- [ ] Open the allocated address.

**Expected result**: The address is allocated at the pool's default length — identical to behaviour before this feature.

### 3. Invalid prefix length is blocked before save

**What this verifies**: Out-of-range / non-integer entries are caught inline and block submission (US3 / SC-003).

**Steps**:

- [ ] With an address pool selected, enter `129` in the **Prefix length** control.
- [ ] Confirm an inline error appears and **Save** is blocked.
- [ ] Try `0` and a non-integer (e.g. `ab`) — same result.
- [ ] Correct the value to a valid length (e.g. `32`).

**Expected result**: Values outside `1–128` (or non-integers) show an inline error and prevent saving; a valid value clears the error and re-enables **Save**.

### 4. Carve a subnet of a specific size from a prefix pool

**What this verifies**: The custom length also works for IP **prefix** pools (US1 / SC-001, SC-004).

**Steps**:

- [ ] On an object with a prefix relationship (or IPAM → create a prefix), set the field to allocate from an IP **prefix** pool.
- [ ] Confirm the **Prefix length · optional** control appears, with the pool default as placeholder.
- [ ] Enter a non-default size (example: `30`), then **Save**.
- [ ] Open the newly created prefix.

**Expected result**: A subnet of exactly the requested size (e.g. `/30`) is carved from the pool — no error, no fallback to the default.

### 5. Control shows only for IP pools, and resets on pool change

**What this verifies**: Gating and reset rules (FR-002, FR-003, FR-009, FR-010, SC-004).

**Steps**:

- [ ] On a from-pool field before any pool is selected → confirm **no** prefix-length control is shown.
- [ ] Select an IP **address** or IP **prefix** pool → the control appears.
- [ ] Enter a length, then switch to a **different** pool → confirm the entered length resets to empty.
- [ ] Clear the pool selection (back to manual entry) → confirm the control disappears.
- [ ] On a field backed by a **number** pool → confirm **no** prefix-length control appears.

**Expected result**: The control is present only while an IP address/prefix pool is selected, resets on pool change, and is absent for number pools.

## Edge Cases

- [ ] **Value equal to the default**: entering exactly the placeholder default behaves the same as leaving it empty.
- [ ] **Reservation conflict (FR-014)**: re-select an address pool that already holds a reservation for this object and enter a *different* length → inline error `its prefix length cannot be changed, only /<n> can be used`. Entering nothing (or the same length) reuses the reservation with no error.
- [ ] **Pool cannot satisfy the length (FR-013)**: enter a valid-but-unsatisfiable length → **Save** submits, the backend allocation error shows inline, and your pool selection + entered length are preserved (no client-side capacity pre-check).
- [ ] **Optional API cross-check**: via `/graphql`, `InfraDeviceCreate(data: { primary_address: { from_pool: { id: "<pool-id>", prefixlen: 32 } } })` allocates at `/32`; omitting `prefixlen` uses the pool default.

## Teardown

No teardown required on the shared preview beyond housekeeping: delete any test devices/addresses you
created, or do the run on a throwaway branch and discard it. On a local stack, `uv run invoke demo.destroy`
removes all containers and volumes.

## Sign-off

- [ ] All scenarios above pass.
- [ ] No unexpected output, warnings, or errors observed.
- [ ] Tester: ______________________  Date: __________
