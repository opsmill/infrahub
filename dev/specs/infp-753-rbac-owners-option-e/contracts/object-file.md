# Object file contract for owners and sources

The storage option does not change this contract. The key names are proposals. An API review fixes them before the pull request on the Python SDK (FR-028).

## Node owners and sources

```yaml
- name: srv-fra-01
  node_metadata:
    owners: [dc-emea, {kind: CoreAccount, name: jdoe}]
    sources: [cmdb-sync]
```

- `owners` left out: no change. `null`: inherit. `[]`: no owner. A list: own owners.
- `sources` left out: no change. `null` and `[]`: no sources.
- A plain name is an account group.
- An account, or a source of another kind, uses the typed form `{kind, name}`.
- Infrahub refuses a plain name that matches both an account and an account group.

## Field owners

```yaml
  description:
    value: Spare server
    owners: []                 # no owner
  ip_addresses:
    owners: [network-emea]     # owners of the relationship field, no peers needed
```

- A field can carry owners without a value.
- Not decided: a relationship that holds both references to existing nodes and owners, for example `rack: {data: fra1-r12, owners: [facilities]}`. The earlier draft did not support it.

## Profiles and object templates

```yaml
- profile_name: EMEA servers
  node_metadata:
    owners: [platform-team]         # own owners of the profile
    target_owners: [server-emea]    # owners given to the nodes
  description:
    owners: [network-emea]          # owners given to the field of the nodes
```

- `target_owners` is valid only on profiles and object templates. The SDK and Infrahub refuse it on other kinds.
- On a profile or an object template, the owners of a field are the owners that it gives to that field of its nodes.

## Refusals

- An owner that is not valid refuses the whole node, with the errors of the GraphQL contract.
- When the change check refuses a node, the load stops at that node (FR-045).
