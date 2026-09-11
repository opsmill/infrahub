When allocating a resource from an IP pool through a relationship that points at the generic
`BuiltinIPAddress` or `BuiltinIPPrefix`, the target object kind can now be chosen instead of
always using the pool's `default_address_type` / `default_prefix_type`. In the UI, the
relationship's existing "Kind" picker selects which concrete kind is allocated; over GraphQL,
pass `address_type` (new on `IPAddressPoolInput`) or `prefix_type` inside `from_pool`.

The requested kind is validated server-side: it must be one of the kinds implementing the
relationship's peer generic, and it cannot be changed on an identifier that already holds a
reservation. Note that `prefix_type` was previously accepted on `IPPrefixPoolInput` without
any validation, so a client sending a kind unrelated to the relationship's peer now receives
an error instead of an unexpectedly-typed node.

Object templates are not covered: a template's `<relationship>_from_resource_pool` link stores
only the pool, so an object created from a template still allocates the pool's default kind.
Sending a target kind or a prefix length on that link previously made the mutation fail, and is
now correctly omitted.
