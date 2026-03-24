# Research: Login/Logout Activity Events

**Branch**: `infp-474-login-logout-events` | **Date**: 2026-03-24

## Questions Resolved

### Q1: Where should events be emitted — inside auth functions or at endpoints?

**Decision**: Emit from API endpoints, not from `authenticate_with_password()` / `signin_sso_account()`.

**Rationale**:
- HTTP context (`client_ip`, `user_agent`) is only available at endpoint level
- Rich account metadata (`account_name`, `account_type`, `groups`, `roles`) is only available after DB lookups inside auth functions
- Solution: refactor auth functions to return `AuthResult` dataclass carrying account metadata; endpoints combine with HTTP context

**Alternatives considered**:
- Emit inside auth functions: would require injecting `Request` or HTTP context deep into non-HTTP code — violates separation of concerns
- Pass HTTP context as parameters to auth functions: couples HTTP layer to auth layer, makes testing harder

---

### Q2: How to pass rich account metadata from auth functions to event-emitting endpoints?

**Decision**: `AuthResult` frozen dataclass returned from `authenticate_with_password()` and `signin_sso_account()`.

```python
@dataclasses.dataclass(frozen=True)
class AuthResult:
    token: models.UserToken
    account_id: str
    account_name: str
    account_type: str
    session_id: uuid.UUID
    groups: list[str]
    roles: list[str]
```

**Rationale**: Frozen dataclass is the correct Infrahub pattern (Constitution III) for internal structured data. The dataclass is truthy so existing `assert await authenticate_with_password(...)` test patterns continue to work.

**Alternatives considered**:
- Named tuple: less ergonomic, no field documentation
- Dict: violates Constitution III (untyped dictionaries for structured data)

---

### Q3: How to handle `AuthenticationError` backward compatibility?

**Decision**: `AuthenticationError(AuthorizationError)` — subclass of existing `AuthorizationError`.

**Rationale**: Existing tests do `pytest.raises(AuthorizationError)`. Making `AuthenticationError` a subclass means those tests continue to pass. HTTP exception handlers already handle `AuthorizationError` → 401 response.

**Alternatives considered**:
- Replace `AuthorizationError` entirely: would break existing tests and callers
- Add `account_id`/`account_name` attributes to `AuthorizationError`: too broad a change to a shared exception

---

### Q4: How to fetch groups and roles for the login event?

**Decision**: `_fetch_account_groups_and_roles(db, account_id, branch)` helper — queries `CoreAccountGroup` with `members__ids` filter, then iterates groups to collect role names.

**Rationale**: `NodeManager.query(schema=CoreAccountGroup, filters={"members__ids": [account_id]})` is the established pattern for reverse relationship lookup (confirmed from `headers__ids`, `thread__ids` patterns elsewhere in codebase). Wrapped in try/except returning empty lists on failure — login should never fail due to group/role fetch errors.

**Alternatives considered**:
- Fetch groups/roles directly from account node relationships: requires loading account node with all peers, more expensive
- Store groups/roles in JWT: already done for authorization, but the source values must be fetched at login time anyway

---

### Q5: What `EventMeta` context to use for auth events?

**Decision**: Construct a minimal `InfrahubContext` with default branch + `AccountSession(auth_type=AuthType.NONE, authenticated=False)`.

**Rationale**: Auth events are not branch-scoped operations. They always occur against the default branch. The account may not yet be authenticated at the point of context construction (especially for failed logins). This matches the pattern used in the OAuth2 callback.

**Alternatives considered**:
- `EventMeta.with_dummy_context(branch)`: available but requires a full `Branch` object; the inline construction is equally clear and avoids importing extra symbols

---

### Q6: How does `NodeNotFoundError` interact with the new `AuthenticationError`?

**Decision**: Preserve `NodeNotFoundError` for "user not found" case; `AuthenticationError` is only for credential failures on existing accounts.

**Rationale**: `NodeNotFoundError` produces a 404 HTTP response in the existing exception handler. If we converted it to `AuthenticationError`, the HTTP status would change to 401 — a behavioral regression. The `AccountLoginFailedEvent` is emitted for both cases with `account_id=None` for the not-found case.

---

### Q7: Which existing event patterns to follow?

**Decision**: Follow `BranchCreatedEvent` / `NodeCreatedEvent` pattern in `backend/infrahub/events/`.

- `ClassVar[str] event_name` on the class
- All payload fields as Pydantic `Field(...)` with descriptions
- `get_resource()` returning a `dict[str, str]` with `prefect.resource.id` and `infrahub.account.*` keys
- `get_payload()` inherited from `InfrahubEvent.model_dump(exclude={"meta"})`

**Rationale**: Consistency with existing event classes. The `get_payload()` default is sufficient — no custom payload logic needed.
