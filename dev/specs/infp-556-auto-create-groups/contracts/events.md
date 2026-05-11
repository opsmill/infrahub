# Contract — Events

Four new event classes in `backend/infrahub/events/group_action.py`: one concrete intermediate (`GroupAutoCreateEvent`) carrying the login context, and three concrete leaves (one per scenario). All four follow the existing `GroupMutatedEvent` shape — typed Pydantic payload + standard `get_event_payload()` returning `{"data": ..., "context": ...}` — and ride the existing `InfrahubEventService.send(event: InfrahubEvent)` interface (no new bus, no new sink).

This structure parallels the existing `GroupMutatedEvent` → `GroupMemberAddedEvent` / `GroupMemberRemovedEvent` pattern in `group_action.py:11,96,104`: a concrete base usable as a parent type, plus class-per-event-name leaves each with their own `event_name` ClassVar.

**Context (`context` field)** for all four classes: standard `InfrahubEvent` context (request id, branch=null since `CoreAccountGroup` is `Branch.AGNOSTIC`, timestamp). `timestamp` is carried here, not in the `data` payload.

## Intermediate: `GroupAutoCreateEvent`

Concrete base for any event emitted by the auto-create-group flow during a login. In practice not emitted standalone — every emission is one of the three concrete leaves below — but a valid type that consumers can subscribe to to receive any of the three.

```python
class GroupAutoCreateEvent(InfrahubEvent):
    """Base for any event emitted by the auto-create-group flow during a login."""
    idp: str = Field(..., description="Originating IdP identifier: <protocol>_<slot>, e.g. oidc_provider1, ldap")
    triggering_user_id: UUID = Field(..., description="The account whose login produced the event")
    triggering_user_name: str = Field(..., description="Login identifier of the triggering account")
    protocol: ExternalAuthProtocol = Field(..., description="OAUTH2 | OIDC | LDAP")
```

## `GroupAutoCreatedEvent` (extends `GroupAutoCreateEvent`) — FR-015

Emitted exactly once per successful auto-creation. NOT emitted on subsequent membership additions to an already-existing auto-created group (FR-015 acceptance scenario 2).

```python
class GroupAutoCreatedEvent(GroupAutoCreateEvent):
    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.group.auto_create.created"

    group_id: UUID
    group_name: str
    source_pattern: str           # raw regex pattern from INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_FILTER
    origin_value: AccountGroupOrigin
```

## `GroupAutoCreateRejectedClaimEvent` (extends `GroupAutoCreateEvent`) — FR-017

Emitted when a claim matches the configured filter but the effective local name fails `CoreAccountGroup` identifier validation. The login still completes; no exception propagates to the end user.

```python
class GroupAutoCreateRejectedClaimEvent(GroupAutoCreateEvent):
    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.group.auto_create.rejected_claim"

    rejected_claim_value: str     # verbatim, length-truncated to a documented upper bound
```

## `GroupAutoCreateCapBreachEvent` (extends `GroupAutoCreateEvent`) — FR-020

Emitted at most once per login, when the per-login soft cap on new-group creation is reached. Auto-creation stops for that login at the cap; the login still completes successfully.

```python
class GroupAutoCreateCapBreachEvent(GroupAutoCreateEvent):
    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.group.auto_create.cap_breach"

    cap_value: int
    dropped_claims: list[str]     # verbatim per-entry, length-truncated
    dropped_count: int
```

## Access control & retention

Inherits from the platform audit-log layer (shared with INFP-474). No feature-specific RBAC; claim values on `GroupAutoCreateRejectedClaimEvent.rejected_claim_value` and `GroupAutoCreateCapBreachEvent.dropped_claims` are stored verbatim with length truncation only (clarification 2026-05-11).

## What does NOT emit an event

- A login whose claims match an already-existing auto-created group (no new creation occurred — FR-015 acceptance scenario 2).
- A login whose claims match no filter pattern (covered by the IFC-922 default-group fallback path, which has its own log entries — out of scope here).
- A login that triggered no auto-creation because the filter setting is unset (feature off).
