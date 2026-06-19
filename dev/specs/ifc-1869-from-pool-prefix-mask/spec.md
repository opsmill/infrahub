# Feature Specification: Custom prefix mask for from-pool allocation

**Feature Branch**: `from-pool-prefix-mask-infp-362`
**Created**: 2026-06-17
**Status**: Implemented (IP address pools)
**Jira**: IFC-1869 (capability 1 of epic IFC-2763 → JPD idea INFP-362)
**Input**: User description: "When a user allocates a Prefix or IP address via from-pool in the Infrahub UI, today the allocation always uses the pool's default prefix length, with no way to request a different mask. This feature lets the user optionally specify the desired prefix length at allocation time, while keeping the pool default as the zero-effort path."

> **Scope as shipped**: This capability covers **IP address pools** (`CoreIPAddressPool`). IP **prefix** pools were deferred — their inline `from_pool` GraphQL input exposes `size`, not `prefixlen`, so honoring a custom length there is a separate enhancement (see Assumptions). References to "prefix or IP address" below describe the original intent; the delivered scope is IP address only.

## Clarifications

### Session 2026-06-17

- Q: How should the interface handle a valid-but-unsatisfiable prefix length (the pool cannot fulfill the requested size)? → A: Submit the request and surface the system's allocation error inline on the form, preserving the user's input so they can adjust; no client-side capacity pre-check.
- Q: Can the prefix length of an already-allocated address be changed by re-allocating from the same pool? → A: No. Pool allocation is idempotent on the reservation identifier: a repeat allocation returns the existing reservation unchanged, including its mask. The custom prefix length therefore applies only at the moment of first allocation. Re-selecting the same pool in an edit form is a no-op, and the prefix-length control is shown only for a pending (not-yet-resolved) allocation. Correcting the mask of an existing address is a direct edit of that address, outside the pool-allocation flow, and is out of scope.
- Q: What happens if a caller requests a prefix length that conflicts with an existing reservation (e.g. switching a relationship back to a pool that already holds a reservation for this object at a different mask)? → A: The allocation is rejected with an inline error (`its prefix length cannot be changed, only /<n> can be used`) rather than silently returning the existing reservation. This preserves idempotency — the reserved `(address, prefix length)` never changes — while making the ignored override visible instead of misleading. The zero-effort path (no length entered) still reuses the existing reservation without error. The cleaner long-term fix is a dedicated endpoint to look up a pool's reserved resources so the UI can show the reserved mask up front; the inline error is the interim backstop.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Allocate with a custom prefix length (Priority: P1)

A network engineer is creating or editing an object and chooses to allocate its IP address or prefix from a resource pool. Rather than accepting the pool's default mask, they want this particular allocation to use a different prefix length — for example, carving a `/28` out of a `/24` prefix pool, or recording a host address as `/32` instead of the pool's `/24` default. They select the pool, enter the desired prefix length, and save; the resulting object is allocated at the length they requested.

**Why this priority**: This is the core capability the feature exists to deliver. Without it there is no feature. It is independently valuable on its own.

**Independent Test**: From an object create/edit form, select a prefix or IP-address pool, enter a prefix length that differs from the pool default, save, and confirm the newly allocated object carries the requested length.

**Acceptance Scenarios**:

1. **Given** a prefix/IP-address field set to allocate from a pool, **When** the user enters a valid prefix length and saves, **Then** the allocated object uses that length rather than the pool default.
2. **Given** a from-pool field, **When** no pool has been selected yet, **Then** no prefix-length control is shown.
3. **Given** a pool is selected, **When** the user views the field, **Then** a prefix-length control is available and labelled as optional.

### User Story 2 - Keep the pool default as the zero-effort path (Priority: P1)

A user who wants the existing behavior should not have to do anything new. They select a pool and save, leaving the prefix length untouched; the allocation uses the pool's default length exactly as it does today. The interface makes clear what default will be applied so the user can decide whether they need to override it.

**Why this priority**: The override must not regress or complicate the common case. Preserving the existing one-step flow is as important as adding the override, so it is also P1.

**Independent Test**: Select a pool, leave the prefix-length control empty, save, and confirm the allocation matches the pool's default length and matches today's behavior.

**Acceptance Scenarios**:

1. **Given** a pool is selected and the prefix-length control is left empty, **When** the user saves, **Then** the allocation uses the pool's default length.
2. **Given** a pool is selected, **When** the user looks at the empty prefix-length control, **Then** the pool's default length is communicated to them (so they know what they will get).
3. **Given** the pool's default length cannot be determined ahead of save, **When** the control is shown, **Then** it still clearly indicates that leaving it empty uses the pool default.

### User Story 3 - Prevent invalid prefix lengths (Priority: P2)

A user enters a prefix length that is not valid for the target address family (for example, a number above the maximum, a negative number, or a non-integer). The interface rejects the entry before submission, explains why, and prevents the user from saving an allocation that the system would reject.

**Why this priority**: Improves correctness and trust, but the feature is still usable without it because the backend ultimately validates the value. Hence P2 rather than P1.

**Independent Test**: Enter an out-of-range or non-integer prefix length and confirm the form shows an inline error and blocks submission until corrected.

**Acceptance Scenarios**:

1. **Given** a from-pool field with a prefix-length control, **When** the user enters a value outside the valid range for the address family, **Then** an inline error appears and saving is blocked.
2. **Given** an invalid value is shown, **When** the user corrects it to a valid length, **Then** the error clears and saving is allowed.

### Edge Cases

- **Changing the selected pool**: any previously entered prefix-length override is reset, so the user does not unknowingly carry a length from a different pool.
- **Clearing the pool / switching back to manual entry**: the prefix-length control and any entered value are removed.
- **Non-IP pools**: when a from-pool target is not an IP prefix or IP address (e.g. a number pool), no prefix-length control is shown.
- **Address family unknown at entry time**: validation falls back to the widest acceptable range and the system rejects values that are impossible for the concrete namespace at save time, with the resulting error surfaced to the user.
- **Value equal to the pool default**: explicitly entering the default length is allowed and behaves identically to leaving it empty.
- **Pool cannot satisfy the requested length**: when a length is valid for the address family but the pool has no free block of that size (or its container cannot carve it), the request is submitted and the system's allocation error is surfaced inline on the form; the user's selection and entered length are preserved so they can adjust. The interface does not pre-check pool capacity.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to optionally specify a prefix length when allocating a Prefix or IP address from a resource pool.
- **FR-002**: The prefix-length control MUST be hidden until a pool has been selected for the field, and MUST appear once a pool is selected.
- **FR-003**: The prefix-length control MUST be shown only when the from-pool target is an **IP address** pool (`CoreIPAddressPool`); it MUST NOT appear for IP prefix pools (deferred) or other pool types (e.g. number pools).
- **FR-004**: When the prefix-length control is left empty, the system MUST allocate using the pool's default prefix length (preserving current behavior).
- **FR-005**: The interface MUST communicate the pool's default prefix length to the user when known, and otherwise MUST clearly indicate that an empty control means "use the pool default".
- **FR-006**: The prefix-length control MUST be clearly marked as optional.
- **FR-007**: The system MUST validate that an entered prefix length is an integer within the accepted range (1–128) before submission, and rely on the pool allocator to reject values impossible for the concrete namespace at save time. *As shipped*: validation is range-based (1–128) and not address-family-aware; per-family tightening (0–32 for IPv4) was not implemented.
- **FR-008**: When an entered prefix length is invalid, the system MUST display an inline error and MUST block submission until it is corrected.
- **FR-009**: Changing the selected pool MUST reset any entered prefix-length override.
- **FR-010**: Clearing the pool selection (returning to manual entry) MUST remove the prefix-length control and discard any entered value.
- **FR-011**: A specified prefix length MUST be applied consistently across every IP-address from-pool entry point that reuses the shared pool picker (relationship pickers, attribute pickers, and any dedicated creation forms). *As shipped*: the control lives inside the shared `PoolSelect`, so all three host fields inherit it automatically.
- **FR-014**: When a caller supplies a prefix length that conflicts with the mask of an existing reservation for the same identifier, the system MUST reject the request with an inline error rather than silently returning the existing reservation. A request with no length, or a length matching the existing reservation, MUST remain idempotent (reuses the reservation, no error).
- **FR-012**: The requested prefix length MUST be carried through to allocation so the resulting object is created at that length.
- **FR-013**: When an allocation fails because the pool cannot satisfy the requested length, the system MUST surface the allocation error inline on the form and MUST preserve the user's pool selection and entered length; it MUST NOT pre-check pool capacity on the client before submission.

### Key Entities *(include if feature involves data)*

- **Resource pool**: a source from which IP prefixes or IP addresses are allocated; has a default prefix length and a target address family/namespace.
- **From-pool allocation request**: a user's intent to allocate from a specific pool, now optionally carrying a requested prefix length in addition to the pool reference.
- **Allocated object**: the IP prefix or IP address created by the allocation, whose mask reflects the requested length when provided, or the pool default otherwise.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can allocate a prefix or IP address from a pool at a non-default length in a single form interaction, without leaving the form or using the API directly.
- **SC-002**: 100% of allocations that leave the prefix-length control empty produce the same result as before the feature (no regression to the default path).
- **SC-003**: Invalid prefix-length entries are caught before submission in 100% of cases for which the address family is known at entry time.
- **SC-004**: The prefix-length control appears in every IP-address from-pool context and in no other from-pool context (not IP prefix pools, not number pools).
- **SC-005**: Users can tell, without saving, what prefix length an empty control will produce whenever the pool's default is available.

## Assumptions

- The work is primarily a user-interface enhancement; the IP address pool's inline `from_pool` input already accepts `prefixlen` and `get_resource` honors it. The only backend change shipped is the FR-014 conflict guard in `CoreIPAddressPool.get_resource`. No GraphQL schema change was needed.
- **IP prefix pools are deferred.** Their inline `from_pool` input exposes `size` (not `prefixlen`), so supporting a custom length there would require a GraphQL input change and backend threading — tracked as a separate enhancement. The UI hides the control for prefix pools rather than sending a value the API rejects.
- **Alternatives considered for FR-014** (and rejected for this capability): (a) releasing the pool reservation when a relationship is re-pointed — rejected as too broad a behavior change (fires on node delete, branch rebase, generator re-runs) and a risk to allocation idempotency; (b) a read-only endpoint to look up a pool's reserved resources so the UI could disable the control up front — viable and cleaner, but a larger change deferred to a follow-up. The inline conflict error is the minimal, idempotency-preserving interim.
- "Prefix length" is the user-facing term (paired with a leading "/"), consistent with how allocation length is referenced elsewhere.
- The pool's default prefix length and address family may not always be available to the interface at entry time; the experience degrades gracefully (neutral default hint, widest-range validation) when they are not.
- Capability 2 (choosing a concrete target kind for generic IP relationships, IFC-2764), member-type selection, and changing a pool's configured default length are out of scope.
- Changing the mask of an already-allocated address via re-allocation is out of scope: allocation is idempotent on the reservation identifier, so the custom prefix length applies only at first allocation (see Clarifications).
- Existing from-pool selection, pool listing, and manual-entry behavior are reused unchanged except for the addition of the optional prefix-length control.
