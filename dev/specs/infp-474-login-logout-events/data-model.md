# Data Model: Login/Logout Activity Events

**Branch**: `infp-474-login-logout-events` | **Date**: 2026-03-24

## Storage

Auth events are stored in the **Prefect event store** (same as all other Infrahub activity events). No Neo4j schema changes are required.

## New Types

### `AuthResult` (internal dataclass)

Returned by `authenticate_with_password()` and `signin_sso_account()` after successful authentication.

```python
@dataclasses.dataclass(frozen=True)
class AuthResult:
    token: models.UserToken      # JWT access + refresh tokens
    account_id: str              # Neo4j node ID of the account
    account_name: str            # Display name / username
    account_type: str            # "User" or "Service"
    session_id: uuid.UUID        # RefreshToken UUID (links login↔logout)
    groups: list[str]            # Group names (empty if fetch fails)
    roles: list[str]             # Role names (empty if fetch fails)
```

## Event Schemas

### `AccountLoggedInEvent`

**Event name**: `infrahub.account.logged_in`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `account_id` | `str` | ✓ | UUID of the account |
| `account_name` | `str` | ✓ | Username |
| `account_type` | `str` | ✓ | USER or SCRIPT |
| `auth_method` | `str` | ✓ | How they authenticated |
| `session_id` | `str` | ✓ | UUID of the session |
| `groups` | `tuple[str]` | ✓ | List of group names/IDs |
| `roles` | `tuple[str]` | ✓ | 	List of role names/IDs |
| `identity_source` | `str \| None` | — | External identity provider name (if applicable) |
| `client_ip` | `str \| None` | — | Source IP address |
| `user_agent` | `str \| None` | — | Browser/client info |
| `timestamp` | `datetime` | ✓ | When login occurred |

**Prefect resource**:
```python
{
    "prefect.resource.id": f"infrahub.account.{account_id}",
    "infrahub.account.name": account_name,
    "infrahub.account.auth_method": auth_method,
    "infrahub.account.session_id": session_id,
}
```

---

### `AccountLoggedOutEvent`

**Event name**: `infrahub.account.logged_out`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `account_id` | `str` | ✓ | UUID of the account |
| `account_name` | `str` | ✓ | Username |
| `session_id` | `str` | ✓ | UUID of the session being terminated |
| `logout_type` | `str` | ✓ | How logout occurred |
| `client_ip` | `str \| None` | — | Source IP address |
| `timestamp` | `datetime` | ✓ | When logout occurred |

**Prefect resource**:
```python
{
    "prefect.resource.id": f"infrahub.account.{account_id}",
    "infrahub.account.name": account_name,
    "infrahub.account.session_id": session_id,
    "infrahub.account.logout_type": logout_type,
}
```

## Session Correlation

The `session_id` field in both `AccountLoggedInEvent` and `AccountLoggedOutEvent` is the UUID of the `RefreshToken` node. This allows administrators to correlate a login event to its corresponding logout event and compute session duration.
