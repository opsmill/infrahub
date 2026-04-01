# Quickstart: Login/Logout Activity Events

**Branch**: `infp-474-login-logout-events` | **Date**: 2026-03-24

## What Was Built

Two new activity events are emitted whenever users authenticate or log out:

| Event | Trigger |
|-------|---------|
| `infrahub.account.logged_in` | Successful login via password, OAuth2, or OIDC |
| `infrahub.account.logged_out` | Explicit user-initiated logout |

## How to Verify

### 1. Trigger a login

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

### 2. Query the event feed (GraphQL)

```graphql
query {
  InfrahubEvent(
    filters: {
      event_type: { in: ["infrahub.account.logged_in"] }
    }
    limit: 10
  ) {
    edges {
      node {
        id
        event
        occurred_at
        account_id
        ... on AccountLoggedInEvent {
          kind
          account_name
          auth_method
          session_id
          groups
          client_ip
          user_agent
        }
      }
    }
  }
}
```

### 3. Trigger a logout

```bash
# First login to get a token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}' | jq -r .access_token)

# Then logout
curl -X POST http://localhost:8000/api/auth/logout \
  -H "Authorization: Bearer $TOKEN"
```

## Webhook Integration

No additional configuration is required. Existing webhook triggers can be configured to fire on these event types:
- `infrahub.account.logged_in`
- `infrahub.account.logged_out`

## Key Design Notes

- **Fire-and-forget**: Event emission is wrapped in `try/except`. A failure to emit an event logs a warning but never blocks login or logout.
- **API key auth excluded**: Per-request API key authentication does not go through the login endpoint and produces no events (FR-008).
- **Session correlation**: The `session_id` field in both login and logout events is the same `RefreshToken` UUID, enabling session duration analysis.
- **SSO provider**: For OAuth2 and OIDC logins, the `identity_source` field contains the configured provider name.
