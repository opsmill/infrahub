Fix the "Resource Pool" tab on the IP prefix detail view so that it now lists both `CoreIPPrefixPool` and `CoreIPAddressPool` pools that have the prefix as a resource. A new `CoreIPPool` generic groups the two pool types and the `BuiltinIPPrefix.resource_pool` relationship now points at it. A database migration retroactively consolidates the IP pool ↔ IP prefix relationships.

**Breaking change for GraphQL clients.** Because `BuiltinIPPrefix.resource_pool` now returns the abstract `CoreIPPool` generic (instead of the concrete `CoreIPAddressPool`), any existing GraphQL queries that selected fields directly under `resource_pool` will need to be updated to use inline fragments for fields that are specific to `CoreIPAddressPool` or `CoreIPPrefixPool`. For example:

```graphql
# Before
query {
  BuiltinIPPrefix {
    edges { node { resource_pool { edges { node { name { value } default_address_type { value } } } } } }
  }
}

# After
query {
  BuiltinIPPrefix {
    edges { node { resource_pool { edges { node {
      name { value }
      ... on CoreIPAddressPool { default_address_type { value } }
      ... on CoreIPPrefixPool  { default_prefix_type  { value } }
    } } } } }
  }
}
```

Fields that exist on the `CoreResourcePool` generic (`name`, `description`) can still be selected directly without a fragment.
