# Contract: Tree Map GraphQL query

**Date**: 2026-10-03 | **Research**: [../research.md](../research.md) R1, R2

No schema change. This is a new client document against the existing `BuiltinIPPrefix` root field.
It is the only network call the feature makes beyond those the detail page already performs.

## Document

Module: `frontend/app/src/entities/ipam/ip-prefixes/api/get-ip-prefix-tree-map-from-api.ts`,
export `GET_IP_PREFIX_TREE_MAP`, built with `graphql` from `@/shared/api/graphql/client` so
gql.tada types it from `schema/schema.graphql`.

```graphql
query GET_IP_PREFIX_TREE_MAP($parentId: ID!, $parentIds: [ID!], $limit: Int) {
  parent: BuiltinIPPrefix(ids: [$parentId]) {
    edges {
      node {
        __typename
        id
        prefix {
          value
          prefixlen
          version
        }
        member_type {
          value
        }
        utilization {
          value
        }
      }
    }
  }
  BuiltinIPPrefix(parent__ids: $parentIds, include_available: true, limit: $limit) {
    count
    edges {
      node {
        __typename
        id
        prefix {
          value
          prefixlen
          version
        }
        member_type {
          value
        }
        utilization {
          value
        }
        is_pool {
          value
        }
        description {
          value
        }
        children {
          count
        }
        ip_addresses {
          count
        }
      }
    }
  }
}
```

Variables: `parentId` is the detail page's prefix id and `parentIds` the same id as a one-element
list (the two root fields take different filter shapes); `limit` is `TREE_MAP_CHILD_LIMIT`.
Request context carries `branch` and `date` as every other query does.

## Response shape

- `parent.edges[0].node`: the parent prefix itself. `prefix.prefixlen` and `prefix.version` give
  its length and family; the client parses only the network address out of `prefix.value`. No
  usable parent is an error state.
- `count`: number of real child prefixes of the parent on this branch, regardless of `limit`.
- `edges[].node.__typename`: a concrete prefix kind (for example `IpamIPPrefix`) for a real child,
  or `InternalIPPrefixAvailable` for a free block.
- Real child: `prefix.value` is the CIDR, `prefix.prefixlen` its length, `prefix.version` `4` or
  `6`, `member_type.value` is `"prefix"` or `"address"`, `utilization.value` is an integer 0 to
  100, `is_pool.value` is a boolean, `children.count` and `ip_addresses.count` are the member
  counts.
- Free block: `prefix.value`, `prefix.prefixlen` and `prefix.version` describe the block,
  `utilization.value` is `null`, counts are `0`, `member_type.value` is a default and must be
  ignored.
- `prefix.num_addresses` exists but is not selected: it is a 32-bit `Int` and overflows for any
  block wider than an IPv4 /1.
- Ordering: by prefix value, real and free interleaved.
- Capping: when `count` is greater than the number of real children in `edges`, the resolver has
  fetched one look-ahead child beyond the page, so free blocks are returned up to that child and
  none beyond it. The client marks the space from the end of the last returned block to the end of
  the parent as not loaded; it never draws it as free or allocated.

## Sample

Captured 2026-10-03 from the public sandbox for parent `10.0.0.0/8`, trimmed to the first four
edges, and brought in line with the current selection: `is_pool`, `prefixlen`, `version` and the
`parent` root field were added afterwards and `display_label` dropped, so those fields show the
values the sandbox returns for them.

```json
{
  "data": {
    "parent": {
      "edges": [
        {"node": {"__typename": "IpamIPPrefix", "id": "1808d316-5e4a-2f1c-d0e8-c51a0f3b9d21",
                  "prefix": {"value": "10.0.0.0/8", "prefixlen": 8, "version": 4},
                  "member_type": {"value": "prefix"}, "utilization": {"value": 1}}}
      ]
    },
    "BuiltinIPPrefix": {
      "count": 3,
      "edges": [
        {"node": {"__typename": "IpamIPPrefix", "id": "1808d317-21bb-8bdf-d0ec-c51b636fbbeb",
                  "prefix": {"value": "10.0.0.0/16", "prefixlen": 16, "version": 4},
                  "member_type": {"value": "address"}, "utilization": {"value": 0}, "is_pool": {"value": false},
                  "description": {"value": null}, "children": {"count": 0},
                  "ip_addresses": {"count": 30}}},
        {"node": {"__typename": "IpamIPPrefix", "id": "1808d318-bc0d-b958-d0e1-c511b808cac8",
                  "prefix": {"value": "10.1.0.0/16", "prefixlen": 16, "version": 4},
                  "member_type": {"value": "prefix"}, "utilization": {"value": 0}, "is_pool": {"value": false},
                  "description": {"value": null}, "children": {"count": 16},
                  "ip_addresses": {"count": 0}}},
        {"node": {"__typename": "IpamIPPrefix", "id": "1808d319-1fe0-d6ae-d0ea-c51f768a4cd7",
                  "prefix": {"value": "10.2.0.0/16", "prefixlen": 16, "version": 4},
                  "member_type": {"value": "prefix"}, "utilization": {"value": 0}, "is_pool": {"value": false},
                  "description": {"value": null}, "children": {"count": 0},
                  "ip_addresses": {"count": 0}}},
        {"node": {"__typename": "InternalIPPrefixAvailable", "id": "18dafbec-c879-c787-11e7-10651a87fdec",
                  "prefix": {"value": "10.3.0.0/16", "prefixlen": 16, "version": 4},
                  "member_type": {"value": "address"}, "utilization": {"value": null}, "is_pool": {"value": false},
                  "description": {"value": null}, "children": {"count": 0},
                  "ip_addresses": {"count": 0}}}
      ]
    }
  }
}
```

## Error handling

- Transport or GraphQL top-level error: the tab renders the shared error screen, as the Children
  tab does.
- A node whose prefix fields are null or whose address does not parse: the use-case drops it with
  a console warning, subtracts it from the child count, and the tile set is built from the rest;
  the tab shows the standard error state only when the parent itself is missing or unparsable.
- `utilization.value` null on a real child: rendered as unknown (FR-014).
