# Phase 1 — Data Model: Auto-create Account Groups (INFP-556)

This feature touches the data model in one place: the addition of a single `origin` attribute on `CoreAccountGroup`. Everything else is configuration or runtime behavior.

---

## Entity: `CoreAccountGroup` (modified)

**Location**: `backend/infrahub/core/schema/definitions/core/permission.py:159–182`
**Branch behavior**: `Branch.AGNOSTIC` (unchanged)
**Uniqueness**: `name__value` (unchanged, inherited from `CoreGroup`)

### New attribute

| Field | Kind | Optional | UI visibility | Default | Read-only from external paths | Validation |
|---|---|---|---|---|---|---|
| `origin` | **`Text`** (free-form string) | **Yes** (nullable) | **`display: extra`** — hidden from the default schema-driven UI view but revealable via the extra/advanced-attributes toggle (FR-012, clarification 2026-05-13) | None — unset is the documented state for any group not created by the auto-creation path | Yes (FR-021) | When set, value is the configured name of the identity provider that triggered auto-creation (no enum constraint — any non-empty string is accepted; provider names are constrained at the configuration layer, not here) |

**Value semantics** (FR-012, FR-013, clarification 2026-05-13):

- The value, when set, holds the **configured name of the identity provider** that authenticated the triggering login — taken verbatim from the auth-flow context (e.g., the configured OIDC provider name from `INFRAHUB_SECURITY_OIDC_PROVIDERS`, the configured OAuth2 provider name, or the configured LDAP provider name).
- There is **no fixed enum value set**. The previously-planned `oidc_provider1` / `oidc_provider2` / `oidc_google` / `oauth2_provider1` / `oauth2_provider2` / `oauth2_google` / `ldap` literals are fully superseded by the Text-with-provider-name model from clarification 2026-05-13.
- There is **no Python `AccountGroupOrigin` enum** in the codebase. The value type at every layer (schema, service, event payload) is `str`.

**Mapping rule from auth flow to attribute value** (clarification 2026-05-13 supersedes the prior 2026-05-11 mapping):

| Source path | Resulting `origin` value |
|---|---|
| OIDC login through a configured OIDC provider | the configured **name** of that OIDC provider (string from settings) |
| OAuth2 login through a configured OAuth2 provider | the configured **name** of that OAuth2 provider (string from settings) |
| Native LDAP login (INFP-105) through a configured LDAP provider | the configured **name** of that LDAP provider (string from settings) |
| OIDC-fronted LDAP/AD login | the configured name of the OIDC provider that authenticated the request (the LDAP-behind-OIDC is opaque to Infrahub) |
| Any other admin-facing creation route (UI, GraphQL, REST, schema load) | **unset** (no value written) |
| Platform bootstrap/seeding (`create_default_account_groups`) | **unset** (no value written) |

### Validation rules

- `origin` is optional — `null`/unset is a valid state for any `CoreAccountGroup` row.
- When set, `origin` is a non-empty `Text` value; the schema validation layer does not enforce a fixed value set (free-form provider name).
- User-supplied `origin` on a create or update operation MUST be rejected or silently ignored (FR-021).
- Once written by the auto-creation path, the value MUST NOT change via any external write path (FR-021). Only the auto-creation path may set it. Admin-facing and bootstrap paths MUST NOT write any value to `origin` (FR-013).

### State transitions

`origin` has two states: unset (initial state for every row) and set-to-a-provider-name-string (terminal — written only by the auto-creation path at first creation). No transitions out of the set state are permitted via external paths. The unset → set transition occurs only during the auto-creation atomic create. A subsequent contribution from a different provider does NOT overwrite the value (Edge Case "Same effective name from two providers" — provenance for additional contributions lives in the auto-creation event log only).

---

## Entity: Filter Pattern (configuration, not persisted)

In-memory only. Constructed at config load.

| Field | Type | Notes |
|---|---|---|
| `raw` | `str` | The pattern as supplied by the admin |
| `compiled` | `re.Pattern` | Result of `re.compile(raw)` — fail at startup if invalid (FR-004) |

Stored as a tuple `tuple[FilterPattern, ...]` on `SecuritySettings` after Pydantic validation. Evaluated in declared order per claim; first match wins (FR-005). At match time, the local name is taken from the `name` named capture group if present, else from the full match (FR-006 / FR-007) — no pre-computed flag needed.

---

## `GroupAutoCreateEvent` (intermediate)

Concrete intermediate base for any event emitted by the auto-creation flow during a login. Modeled after the existing `GroupMutatedEvent` in `backend/infrahub/events/group_action.py:11` — a concrete event class that also serves as the base for more-specific siblings. Carries the login-context fields shared by all three concrete events below. Timestamp lives on the platform's standard event `context` (via `meta.context`), not in `data`.

| Field | Type | Notes |
|---|---|---|
| `idp` | `str` | The **configured name** of the originating identity provider (free-form string from settings — e.g., `"AzureAD-corp"`, `"OktaProd"`, `"corp-ldap"`). Same value that is written to the new group's `origin` attribute. Supersedes the prior `<protocol>_<slot>` shape from the enum-era reconcile. |
| `triggering_user_id` | `UUID` | The account whose login produced the event |
| `triggering_user_name` | `str` | Login name of the triggering account |
| `protocol` | `ExternalAuthProtocol` | `OAUTH2 \| OIDC \| LDAP` |

## `GroupAutoCreatedEvent` — FR-015

Extends `GroupAutoCreateEvent` with:

| Field | Type | Notes |
|---|---|---|
| `group_id` | `UUID` | The newly-created `CoreAccountGroup` node id |
| `group_name` | `str` | Effective local name |
| `source_pattern` | `str` | The raw regex pattern that matched (verbatim from config) |
| `origin_value` | `str` | The configured identity-provider name written to the new group's `origin` attribute (same string as `idp` on the base event; carried explicitly here for self-contained event payloads). Type is `str` — no enum (clarification 2026-05-13). |

Emitted once per successful auto-creation (creation only, not on subsequent membership adds — FR-015).

## `GroupAutoCreateRejectedClaimEvent` — FR-017

Extends `GroupAutoCreateEvent` with:

| Field | Type | Notes |
|---|---|---|
| `rejected_claim_value` | `str` | The offending claim. Verbatim, length-truncated to a documented upper bound |

Emitted when a claim matches the configured filter but the effective local name fails `CoreAccountGroup` identifier validation. The login still completes (FR-017).

## `GroupAutoCreateCapBreachEvent` — FR-020

Extends `GroupAutoCreateEvent` with:

| Field | Type | Notes |
|---|---|---|
| `cap_value` | `int` | The active per-login soft cap that was reached |
| `dropped_claims` | `list[str]` | The claim values that were dropped because the cap was reached. Verbatim per-entry, length-truncated |
| `dropped_count` | `int` | Total number of dropped claims for this login |

Emitted at most once per login. The login still completes successfully (FR-020).

---

## Configuration (not data, recorded here for completeness)

Two new fields on `SecuritySettings` (`backend/infrahub/config.py:743+`, env prefix `INFRAHUB_SECURITY_`):

| Setting | Type | Default | Notes |
|---|---|---|---|
| `auto_create_groups_filter` | `str \| list[str] \| None` | None | Unset/empty = feature off (FR-001, FR-003). Validated and compiled at startup (FR-004) |
| `auto_create_groups_max_per_login` | `int` | `50` | Per-login soft cap on new creations (FR-020) |

No new dedicated enable toggle — the filter setting is the sole activation surface (FR-001, clarification 2026-05-05).
