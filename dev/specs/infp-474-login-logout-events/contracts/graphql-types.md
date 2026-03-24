# GraphQL Contracts: Login/Logout Activity Events

**Branch**: `infp-474-login-logout-events` | **Date**: 2026-03-24

These types are registered in `EVENT_TYPES` in `backend/infrahub/graphql/types/event.py` and are resolved automatically by `EventNodeInterface.resolve_type()` when querying the activity event feed.

## New GraphQL ObjectTypes

### `AccountLoggedInEventType`

```graphql
type AccountLoggedInEvent implements EventNodeInterface {
  # --- EventNodeInterface fields (inherited) ---
  id: String!
  event: String!
  branch: String
  account_id: String
  level: Int!
  primary_node: RelatedNode
  related_nodes: [RelatedNode!]!
  has_children: Boolean!
  parent_id: String

  # --- AccountLoggedInEvent-specific fields ---
  account_name: String!
  account_type: String!
  auth_method: String!
  session_id: String!
  groups: [String!]!
  roles: [String!]!
  sso_provider: String
  client_ip: String
  user_agent: String
  timestamp: DateTime!
  payload: GenericScalar!
}
```

### `AccountLoginFailedEventType`

```graphql
type AccountLoginFailedEvent implements EventNodeInterface {
  # --- EventNodeInterface fields (inherited) ---
  id: String!
  event: String!
  branch: String
  account_id: String
  level: Int!
  primary_node: RelatedNode
  related_nodes: [RelatedNode!]!
  has_children: Boolean!
  parent_id: String

  # --- AccountLoginFailedEvent-specific fields ---
  attempted_identifier: String!
  auth_method: String!
  failure_reason: String!
  client_ip: String
  user_agent: String
  timestamp: DateTime!
  payload: GenericScalar!
}
```

### `AccountLoggedOutEventType`

```graphql
type AccountLoggedOutEvent implements EventNodeInterface {
  # --- EventNodeInterface fields (inherited) ---
  id: String!
  event: String!
  branch: String
  account_id: String
  level: Int!
  primary_node: RelatedNode
  related_nodes: [RelatedNode!]!
  has_children: Boolean!
  parent_id: String

  # --- AccountLoggedOutEvent-specific fields ---
  account_name: String!
  session_id: String!
  logout_type: String!
  client_ip: String
  user_agent: String
  timestamp: DateTime!
  payload: GenericScalar!
}
```

## EVENT_TYPES Registration

```python
events.AccountLoggedInEvent.event_name: AccountLoggedInEventType,    # "infrahub.account.logged_in"
events.AccountLoginFailedEvent.event_name: AccountLoginFailedEventType,  # "infrahub.account.login_failed"
events.AccountLoggedOutEvent.event_name: AccountLoggedOutEventType,  # "infrahub.account.logged_out"
```

## Example Query

```graphql
query GetAuthEvents {
  InfrahubEvent(
    filters: {
      event_type: { in: ["infrahub.account.logged_in", "infrahub.account.login_failed", "infrahub.account.logged_out"] }
    }
    limit: 100
  ) {
    edges {
      node {
        id
        event
        account_id
        ... on AccountLoggedInEvent {
          account_name
          auth_method
          session_id
          groups
          client_ip
          timestamp
        }
        ... on AccountLoginFailedEvent {
          attempted_identifier
          auth_method
          failure_reason
          client_ip
          timestamp
        }
        ... on AccountLoggedOutEvent {
          account_name
          session_id
          logout_type
          timestamp
        }
      }
    }
  }
}
```
