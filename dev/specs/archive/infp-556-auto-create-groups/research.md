# Phase 0 — Research: Auto-create Account Groups (INFP-556)

All "NEEDS CLARIFICATION" items from the plan's Technical Context were resolved by codebase exploration and the prior three clarification sessions on `spec.md`. The decisions below capture the technical posture for implementation.

---

## R1. Provider-slot → `origin` enum mapping

**Decision**: Use the existing `Oauth2Provider` and `OIDCProvider` Python enums in `backend/infrahub/config.py:70–79` as the source of truth. Each enum value (`PROVIDER1`, `PROVIDER2`, `GOOGLE`) maps verbatim to the literal slot name (`provider1`, `provider2`, `google`); concatenated with the protocol prefix (`oidc_` or `oauth2_`) it produces the `origin` enum value. A tiny `mapper.py` module wraps this concatenation.

**Rationale**: The "documented mapping rule" referenced in Clarifications Session 2026-05-05 was clarified explicitly on 2026-05-11. The mapping is 1:1 with no inference from issuer URLs or metadata. The provider slot values already exist; the new schema enum literals were designed to mirror them.

**Alternatives considered**:
- Issuer-URL inference (rejected — brittle; "Google's standard issuer URL" is not stable across hosted GSuite tenants)
- Admin-configured per-provider `origin_value` field (rejected — added admin surface for zero gain since slot names are already fixed)

---

## R2. Native LDAP (INFP-105) integration surface

**Decision**: Treat native LDAP as a future caller of the same `auth_groups.service.autocreate_groups_for_login(...)` function. Provide a `protocol` parameter that takes one of `OAUTH2 | OIDC | LDAP` from the existing `ExternalAuthProtocol` enum. When INFP-105 lands, its login handler calls the same service with `protocol=LDAP`; `origin` is set to `"ldap"`. OIDC-fronted LDAP (per the Provider-scope assumption) explicitly uses the OIDC slot value, not `ldap` (resolved 2026-05-11).

**Rationale**: One service interface for both shipping protocols and the new one. Avoids duplicating the regex-and-create logic per protocol.

**Alternatives considered**:
- Inline auto-creation in each protocol handler (rejected — three near-identical copies; violates Principle VII)
- Wait for INFP-105 to be merged first and design jointly (rejected — INFP-105 owners are aligned via the shared 1.10 enterprise-identity story; the spec already locks the integration shape)

---

## R3. Concurrency-safe atomic find-or-create

**Decision**: A three-layer find-or-create pattern, each layer defending against a distinct failure mode. The full worst-case shape is below; layer 1 is an optimization conditional on benchmarks (see "Implementation note" further down).

```text
# Layer 1 — fast path, no lock (SC-004 optimization)
existing = find_by_name(name)
if existing:
    add_user_to_group(existing, user)
    return                                            # 99% of matching-claim logins land here

# Layer 2 — slow path, under the distributed lock (FR-011 correctness)
async with lock.registry.get(name=name, namespace="auto-create-group"):
    existing = find_by_name(name)                     # re-check; the gap before acquiring could be long
    if existing:
        add_user_to_group(existing, user)
        return

    # Layer 3 — guard against cross-path races + lock-TTL expiry
    try:
        new_group = Node.init(...).save()             # full Node lifecycle: defaults, lineage, hooks
    except UniqueConstraintViolation:
        existing = find_by_name(name)
        add_user_to_group(existing, user)
        return                                        # no GroupAutoCreatedEvent on this branch

    add_user_to_group(new_group, user)
    emit(GroupAutoCreatedEvent, ...)                  # only on actual create
```

The lock follows the existing distributed-lock pattern (`auth.py:242` uses `lock.registry.get(name=..., namespace="sso-account")` for external-identity uniqueness — reuse the same primitive with namespace `auto-create-group`). The `Node.init(...).save()` call goes through the full lifecycle exactly as `create_accounts_group` does today (`backend/infrahub/core/initialization.py:512–540`). Membership add follows the existing `signin_sso_account` path (`backend/infrahub/auth.py:310–321`).

**What each layer defends against**:

| Layer | Concern | Without it |
|---|---|---|
| 1. Fast path | Lock-acquisition overhead on the hot path (every login of every existing-group member) | SC-004 "no measurable additional latency" likely violated |
| 2. Under-lock check | Two auto-creation flows racing on the same brand-new claim | FR-011 violated (duplicate groups possible) |
| 3. Constraint-violation catch | Cross-code-path race (admin UI / bootstrap / schema-load) or lock TTL expiring mid-`save()` | `UniqueConstraintViolation` propagates as a 5xx to the user's login |

**Rationale**: Pattern (lock + check-under-lock) is already used in `auth.py:242` for external-identity uniqueness — no new concurrency primitive. The three layers each address a distinct, real failure mode (not hypothetical): SC-004 names the perf goal, FR-011 the concurrency contract, and Infrahub has multiple `CoreAccountGroup` creation paths (manual, bootstrap) that don't share this lock, so the constraint-violation case can occur in production. Neo4j's uniqueness index on `name__value` (inherited from `CoreGroup`) makes layer 3 cheap to implement — the index does the detection; we just have to catch the exception.

**Critical post-write invariant**: `GroupAutoCreatedEvent` MUST only fire on the *actual create* branch — never on the re-fetch-after-conflict branch nor on the existing-group branches (FR-015 says no event on subsequent encounters). Membership add, by contrast, happens on every branch.

**Implementation note — benchmark before locking in layer 1**: Layer 1 is purely an optimization. The implementer should measure during functional testing:

1. Baseline login latency (feature off).
2. With single-layer locking (no outer check; layers 2+3 only).
3. With three layers.

If (2) shows "no measurable additional latency" vs (1) per SC-004's contract, layer 1 should be dropped — the two-layer version is simpler and meets the spec. If (2) shows a measurable delta, layer 1 stays. Lock acquisition cost is implementation-dependent (depends on whether `lock.registry` is in-process, Redis-backed, or Postgres-advisory under the hood), so this is a deliberate decision deferred to implementation.

**Alternatives considered**:
- Cypher `MERGE` only (rejected — `CoreAccountGroup` creation requires the full `Node` lifecycle, including attribute defaults, lineage, and event emission hooks; `MERGE` would bypass that).
- Single-layer locking with no constraint-violation catch (rejected — leaves a real 5xx-shaped failure mode for cross-code-path races; the catch is cheap because the index is already there).
- Constraint-violation catch with no lock (rejected — would work for correctness via the uniqueness index, but every concurrent first-login would emit a `GroupAutoCreatedEvent` for the winning side and trip a violation for the losing side, polluting the audit log with spurious failed-creation traces; the lock keeps the audit log clean).

---

## R4. Schema migration for `origin` backfill

**Decision**: New `GraphMigration` subclass under `backend/infrahub/core/migrations/graph/mNNN_set_account_group_origin.py` modeled exactly after `m069_set_comment_thread_created_by_on_node.py`. Cypher: `MATCH (g:CoreAccountGroup) WHERE g.origin__value IS NULL SET g.origin__value = "manual"`. Minimum version: whatever is current + 1. Validation step asserts zero remaining null `origin__value` after the SET.

**Rationale**: `m069` is the most recent analog (backfilling an attribute on existing nodes). Following the exact template keeps the migration reviewable and matches the established pattern (Principle VII).

**Alternatives considered**:
- Default-value-on-attribute approach without migration (rejected — pre-existing rows would still need a backfill to satisfy SC-005's "no nulls" contract)
- Per-branch migration (rejected — `CoreAccountGroup` is `Branch.AGNOSTIC`)

---

## R5. `origin` attribute system-managed read-only enforcement

**Decision**: Declare `origin` on the `CoreAccountGroup` schema with kind `Dropdown` (existing Infrahub schema attribute kind for enum-like static value sets, used elsewhere on `CoreAccountGroup`'s `group_type` field). Use schema flags / metadata to mark it as system-managed so GraphQL mutations, REST writes, and schema loads cannot set or modify it. Validate at the Pydantic input layer (reject user-supplied `origin` on create/update with a clear validation error) and at the Cypher write layer (server-set value always wins for `origin__value`).

**Rationale**: Reuses an existing schema kind (Principle VII). The `Dropdown` kind is what other `CoreAccountGroup` enum fields already use. Read-only enforcement at two layers (input validation + write-layer override) defends against bypass via direct GraphQL or schema-load paths (FR-021).

**Alternatives considered**:
- New custom "system-managed" schema kind (rejected — premature abstraction; one attribute does not justify a new kind)
- Read-only at API layer only (rejected — schema loads bypass the API; need a deeper enforcement point)

---

## R6. Event emission for auto-creation, skipped claims, and cap breaches

**Decision**: Add four event classes in `backend/infrahub/events/group_action.py`: a concrete intermediate `GroupAutoCreateEvent` extending `InfrahubEvent` and carrying the login-context fields (`idp`, `triggering_user_id`, `triggering_user_name`, `protocol`), plus three concrete leaves — `GroupAutoCreatedEvent` (FR-015, success), `GroupAutoCreateRejectedEvent` (FR-017, claim rejected by name validation), `GroupAutoCreateCappedEvent` (FR-020, per-login cap reached). Each leaf has its own `event_name` ClassVar under the `EVENT_NAMESPACE.group.auto_create*` prefix (`auto_created`, `auto_create_rejected`, `auto_create_capped`). Claim values on the two warning leaves are stored verbatim length-truncated (no hashing, no feature-specific RBAC, per 2026-05-11 clarification). `timestamp` lives on `meta.context`, not in the `data` payload.

**Rationale**: Matches the existing `GroupMutatedEvent` → `GroupMemberAddedEvent` / `GroupMemberRemovedEvent` pattern in `group_action.py:11,96,104` — class-per-event-name leaves with a concrete intermediate parent. The intermediate dedupes the four login-context fields across the three concretes; the per-class leaf design avoids `| None` payload fields that encode "valid only for subtype X" and lets mypy see `cap_value: int` (not `int | None`) on the cap-breach event. All three leaves share an `auto_create` event-name prefix (`auto_created`, `auto_create_rejected`, `auto_create_capped`) so audit consumers can subscribe by pattern.

**Alternatives considered**:
- One event class with a status field (rejected — auditors typically filter by event type; mixing normal and warning under one type forces consumers to filter on a payload field).
- Two event classes (success + single warning with subtype discriminator) (rejected on review — class-per-event-name matches the existing `GroupMemberAddedEvent` / `GroupMemberRemovedEvent` precedent and avoids `| None` payload fields and an invented `reason` field that duplicates the discriminator).
- Underscore-prefixed abstract intermediate (`_GroupAutoCreateLoginEventBase`) (rejected — has no precedent in the codebase; the existing pattern uses concrete intermediates like `GroupMutatedEvent`).

---

## R7. Filter configuration shape

**Decision**: `INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_FILTER` is a `str | list[str] | None` Pydantic field on `SecuritySettings`. A field validator compiles every supplied pattern at config load time (`re.compile`); compilation errors raise `pydantic.ValidationError` naming the failing setting and the regex error (FR-004); the existing `config.load_and_exit` wrapper (`backend/infrahub/config.py:1221`) catches `ValidationError` at server startup, prints the offending field and message, and calls `sys.exit(1)` — the FastAPI server does not start. An unset / empty-string / whitespace-only / empty-list value means "feature off" and is NOT a configuration error (FR-001, FR-003). The validator stores a compiled `tuple[re.Pattern, ...]` on a private attribute so the auth hook does not re-compile per request.

**Rationale**: Matches the existing `SecuritySettings` style (`oauth2_providers: list[Oauth2Provider]` already uses list-shaped optional config). Compile-once-at-startup is essential for performance under SC-004.

**Alternatives considered**:
- Only single-pattern (rejected — admins with multi-namespace IdPs need ordered alternatives, see FR-005)
- Lazy compilation (rejected — defeats FR-004's "fail loud at startup")

---

## R8. Per-login cap configuration

**Decision**: `INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_MAX_PER_LOGIN: int` on `SecuritySettings` with default `50` (per FR-020). Implemented as a counter inside `autocreate_groups_for_login` that increments on each successful new-group creation only — assignments to already-existing groups are uncounted. When the counter reaches the cap mid-iteration, remaining matching claims for that login are dropped, a single `GroupAutoCreateCappedEvent` is emitted carrying the cap value and the verbatim length-truncated dropped claims, and the login completes successfully (FR-020).

**Rationale**: Per-login locality keeps the implementation a simple in-method counter; no instance-wide rate-limiting state is introduced (out-of-scope per the spec).

**Alternatives considered**:
- Hard cap that fails the login (rejected by the spec — user already authenticated)
- Per-instance / per-hour cap (rejected by the spec — explicitly out of scope)

---

## R9. Native LDAP timing — sequencing risk

**Decision**: Implement and merge INFP-556 against the OIDC + OAuth2 surfaces first. Add the `LDAP` branch in `autocreate_groups_for_login`'s `protocol` parameter immediately so the API is stable; the actual LDAP call site lands with INFP-105. The schema enum already includes `ldap` (FR-012), so the schema migration is not blocked on INFP-105 timing.

**Rationale**: Decouples the two stories on the merge axis while preserving the 1.10 ship-together story. The enum value `ldap` is present from day one so a later INFP-105 PR only adds a call site, not a schema change.

**Alternatives considered**:
- Joint single PR (rejected — couples two large changes; PR review overhead and rollback granularity worsen)
- Defer `ldap` enum value until INFP-105 lands (rejected — would require a follow-up schema migration just to add one enum literal, churn for no gain)
