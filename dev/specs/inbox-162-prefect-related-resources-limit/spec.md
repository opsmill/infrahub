# Feature Specification: Align Infrahub's event related-resource cap with Prefect's effective limit

**Feature Branch**: `pha/INBOX-162`

**Created**: 2026-09-07

**Status**: Draft

**Input**: INBOX-162 — Make `backend/infrahub/events/limits.py` read Prefect's effective max-related-resources setting instead of hardcoding 500.

## Context

Infrahub emits Prefect events for node and group mutations. Prefect rejects any event whose
related-resource list exceeds a configured maximum, and it does so *silently* — the rejection
happens client-side inside the Infrahub process, is swallowed by a bare `except Exception` in
Prefect's `emit_event`, and the mutation itself still succeeds. The result is a lost event: no
automation, no trigger, no webhook, no activity-feed entry. Infrahub therefore has to know that
maximum and truncate below it before handing the event over. That is the whole job of
`backend/infrahub/events/limits.py`, introduced by #9793 to close #9794.

The module currently derives that maximum from a single raw environment-variable read with a
hardcoded fallback of 500. Both halves of that are wrong, and the failure mode of being wrong is
the exact silent event loss the module exists to prevent.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Events survive on a deployment that does not set the environment variable (Priority: P1)

An operator runs Infrahub without the shipped container image — a source checkout, a custom image,
a Helm chart of their own, or a local development run. They never set
`PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES`, so Prefect enforces its own default of 100.
They perform a mutation that touches a few hundred related nodes.

Today Infrahub believes the cap is 500, truncates to a budget derived from 500, hands Prefect an
event well above 100, and Prefect discards it silently. The operator sees the mutation succeed and
no event: no automation fires, and nothing appears in the activity feed. Nothing is logged as an
error by Infrahub.

**Why this priority**: This is the defect. It re-opens #9794 for every deployment that is not the
shipped image, and it fails silently, so operators cannot diagnose it.

**Independent Test**: With no related-resources environment variable or setting configured, emit a
node mutation event carrying more related resources than Prefect's default allows, and assert that
Infrahub's own truncation keeps the event within what Prefect accepts.

**Acceptance Scenarios**:

1. **Given** no related-resources override is configured anywhere, **When** Infrahub computes the
   maximum related resources an event may carry, **Then** it reports Prefect's own default (100),
   not 500.
2. **Given** no override is configured, **When** a node mutation produces more related resources
   than the budget derived from that maximum, **Then** Infrahub truncates the event to that budget
   and the event is accepted by Prefect rather than silently discarded.

---

### User Story 2 - Shipped-image behaviour is unchanged (Priority: P1)

An operator runs the shipped Infrahub image, which sets the maximum to 500. Their events must keep
behaving exactly as they do today — the same cap, the same budget, the same truncation threshold.

**Why this priority**: Equal to P1 above, because a fix that changes the shipped deployment's
event capacity would be a regression for every existing user, and would be a far more visible one
than the bug being fixed.

**Independent Test**: With the maximum configured to 500 — by the same environment variable the
image sets — assert the derived cap and truncation threshold match today's values.

**Acceptance Scenarios**:

1. **Given** the maximum is configured to 500 via the environment variable the shipped image sets,
   **When** Infrahub computes the maximum, **Then** it reports 500.
2. **Given** the maximum is configured to 500, **When** a node mutation exceeds the derived
   budget, **Then** it truncates at the same threshold it does today.

---

### User Story 3 - Infrahub's cap follows however the operator configured Prefect (Priority: P2)

An operator configures the related-resources maximum by a means other than the one environment
variable Infrahub happens to read — the second environment variable Prefect accepts as an alias
for the same setting, a Prefect profile, or a Prefect configuration file. Prefect enforces the
value they set; Infrahub must use the same value.

**Why this priority**: P2 because it is a latent divergence rather than an active default-path
break, but it is the same silent-loss failure class: whenever Infrahub's number disagrees with the
number Prefect enforces and Infrahub's is the larger, events are lost silently.

**Independent Test**: Configure the maximum through Prefect's settings mechanism rather than the
single environment variable, and assert Infrahub reports the configured value.

**Acceptance Scenarios**:

1. **Given** the maximum is set through Prefect's own settings mechanism, **When** Infrahub
   computes the maximum, **Then** it reports the configured value.
2. **Given** the maximum is set through the alias environment variable Prefect also honours,
   **When** Infrahub computes the maximum, **Then** it reports that value.

---

### Edge Cases

- **No configuration at all** — Infrahub reports Prefect's documented default (100). This is the
  primary bug being fixed, covered by User Story 1.
- **A non-positive configured value** (`0`, a negative number) — a value Prefect could not
  meaningfully enforce. Infrahub falls back to the documented default rather than deriving a
  nonsensical budget, preserving the module's existing defensive behaviour.
- **A malformed configured value** (non-numeric) — rejected at startup by Prefect's own settings
  validation, before any Infrahub code runs. Infrahub adds no fallback here: a typo now fails
  loudly instead of silently selecting a wrong ceiling, which is the same class of silence this
  change exists to remove. This is an intentional change from today's behaviour, where a malformed
  value was quietly treated as 500.
- **The configured maximum is very small** (1, 20) — the derived budget and submission chunk size
  are already floored at 1 by the existing helpers; that behaviour is unchanged.
- **The setting changes during process lifetime** (a test override, a settings context) — the
  maximum is read live on each call, so callers observe the current value rather than a value
  captured at import.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST derive its maximum-related-resources value from the limit Prefect
  actually enforces, resolved through Prefect's own configuration mechanism, rather than by reading
  a single environment variable directly.
- **FR-002**: The system MUST report Prefect's own documented default (100) when the operator has
  configured no value, replacing the current 500.
- **FR-003**: The system MUST NOT retain 500 as a default, fallback, or literal anywhere in the
  limits module. 500 remains only where the shipped image explicitly configures it.
- **FR-004**: The system MUST honour every means by which an operator can set the limit for
  Prefect — both environment-variable names Prefect accepts for it, and Prefect's own
  configuration sources.
- **FR-005**: The system MUST fall back to the documented default (100) when the configured value
  is absent or non-positive, without raising and without breaking event emission.
- **FR-005a**: A configured value that is not a number MUST be rejected at startup rather than
  silently substituted. Prefect itself refuses to construct its settings from such a value, so the
  process cannot start — which is the correct outcome: a misconfiguration that used to be silently
  replaced by a wrong ceiling is now impossible to miss. Infrahub MUST NOT add a fallback that
  masks it.
- **FR-006**: The system MUST leave the shipped image's configured value untouched, so deployments
  running the shipped image keep their current event capacity exactly.
- **FR-007**: The derived related-resource budget, the submission chunk size, and the run-context
  reservation MUST keep their current semantics and their current call signatures. Only the source
  of the maximum changes.
- **FR-008**: The maximum MUST be resolved at call time, so a value changed after import — in
  particular by a test-time override — is observed by every caller.
- **FR-009**: The change MUST be accompanied by a user-facing changelog entry, since it alters
  event-delivery behaviour on deployments that do not set the limit.

### Key Entities

- **Maximum related resources**: the per-event ceiling Prefect enforces on the related-resource
  list. Owned and enforced by Prefect; Infrahub only reads it.
- **Related-resource budget**: the number of related resources an Infrahub event may carry when it
  leaves Infrahub, held below the maximum to leave room for the resources Prefect appends
  afterwards. Derived from the maximum.
- **Submission chunk size**: the number of node ids one coalesced recompute submission may carry.
  Also derived from the maximum.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a deployment with no related-resources configuration, a node mutation touching
  more related resources than Prefect's default allows still produces exactly one delivered event
  — zero silently dropped events, where today all such events are dropped.
- **SC-002**: On a deployment configured with 500, the truncation threshold is byte-for-byte the
  value in use before this change — zero behavioural difference for shipped-image users.
- **SC-003**: The value Infrahub truncates against equals the value Prefect enforces for every
  configuration mechanism an operator can use, verified across at least the unset case, both
  environment-variable names, and Prefect's own settings mechanism.
- **SC-004**: An absent, zero, negative, or non-numeric configured value produces the documented
  default rather than an exception or a nonsensical budget.
- **SC-005**: Every pre-existing test covering the limits module, node events, group events, and
  coalesced-recompute submission continues to pass, with each case's original intent preserved.

## Assumptions

- Prefect's documented default for this limit is 100, and Prefect's own configuration mechanism is
  the authoritative way to read the effective value. Verified against the Prefect version pinned
  in this repository rather than assumed from documentation.
- The two environment-variable names for this limit are aliases for one setting, so honouring the
  setting honours both automatically; no separate per-name handling is required.
- Prefect is already a dependency of the backend. Reading more of its public configuration surface
  introduces no new dependency.
- The shipped image's explicit configuration is intentional and stays as-is. This change is about
  what happens when that configuration is *absent*, not about changing what it says.
- Truncation continues to be the response to an over-budget event. Chunking or splitting events so
  that no related resource is lost is a larger behavioural change and is out of scope here.
- The group-event path (`GroupMutatedEvent`), which is the main subject of the source issue and
  does not consult the limits module at all, is out of scope. This change covers only the
  divergence in how the limit itself is resolved.

## Out of Scope

- Fixing the unbounded group-event related-resource list (the primary subject of issue #10127).
- Changing the shipped image's configured maximum.
- Replacing truncation with chunking, or otherwise avoiding the loss of related resources beyond
  the budget.
- Surfacing the truncation to users through any new channel; the existing warning log stays as-is.
