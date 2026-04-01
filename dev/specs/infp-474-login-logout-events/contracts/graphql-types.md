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
  kind: String!
  account_name: String!
  account_type: String!
  auth_method: String!
  session_id: String!
  groups: [String!]!
  roles: [String!]!
  identity_source: String
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
  kind: String!
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
events.AccountLoggedOutEvent.event_name: AccountLoggedOutEventType,  # "infrahub.account.logged_out"
```

## Example Query

```graphql
query GetAuthEvents {
  InfrahubEvent(
    filters: {
      event_type: { in: ["infrahub.account.logged_in", "infrahub.account.logged_out"] }
    }
    limit: 100
  ) {
    edges {
      node {
        id
        event
        account_id
        ... on AccountLoggedInEvent {
          kind
          account_name
          auth_method
          session_id
          groups
          client_ip
          timestamp
        }
        ... on AccountLoggedOutEvent {
          kind
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
