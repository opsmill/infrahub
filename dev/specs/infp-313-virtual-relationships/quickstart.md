# Quickstart: Virtual Relationships

## What Are Virtual Relationships?

Virtual relationships let you define a shortcut path through your schema so you can query deeply nested data in a single step. Instead of traversing `device → bays → line_cards → modules → interfaces` manually, you define a virtual relationship on Device and query `device.all_interfaces` directly.

## Define a Virtual Relationship

Add a `virtual_relationships` section to your schema YAML:

```yaml
nodes:
  - name: Device
    namespace: Infra
    attributes:
      - name: hostname
        kind: Text
        unique: true
    relationships:
      - name: bays
        peer: InfraBay
        cardinality: many
        kind: Component
    virtual_relationships:
      - name: all_interfaces
        label: "All Interfaces"
        description: "Interfaces across all bays, line cards, and modules"
        path: bays__line_cards__modules__interfaces
```

The `path` field uses double-underscore notation to define the traversal. Each segment is a relationship name.

## Query via GraphQL

Virtual relationships work exactly like regular relationships in queries:

```graphql
query {
  InfraDevice(ids: ["my-device-id"]) {
    edges {
      node {
        hostname { value }
        all_interfaces {
          count
          edges {
            node {
              name { value }
              enabled { value }
            }
          }
        }
      }
    }
  }
}
```

Filtering and pagination work the same way:

```graphql
query {
  InfraDevice(ids: ["my-device-id"]) {
    edges {
      node {
        all_interfaces(enabled__value: true, limit: 10) {
          count
          edges {
            node {
              name { value }
            }
          }
        }
      }
    }
  }
}
```

## View in UI

Navigate to any Device in the Infrahub UI. Virtual relationships appear as tabs alongside regular relationships. Click the "All Interfaces" tab to see all interfaces collected from the traversal path.

## Add via Schema Extension

You can also add virtual relationships to existing nodes without modifying their base schema:

```yaml
extensions:
  nodes:
    - kind: InfraDevice
      virtual_relationships:
        - name: affected_services
          label: "Affected Services"
          path: interfaces__circuits__containers__services
```

## Key Facts

- **Read-only**: Virtual relationships are for querying only. You cannot create or modify nodes through them.
- **No duplication**: No extra data is stored. Results are computed from existing relationships.
- **Branch-aware**: Virtual relationships resolve using the data in the queried branch.
- **Always consistent**: Results always reflect the current state of the data.
- **Path limits**: Minimum 2 segments, maximum 10 segments per path.
