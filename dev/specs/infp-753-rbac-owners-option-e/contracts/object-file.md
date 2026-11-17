# Object file contract for owners and sources

The storage option does not change this contract. The key names are proposals. An API review fixes them before the pull request on the Python SDK (FR-028).

Decision of 2026-11-16 ([provisional-decisions.md](../provisional-decisions.md), PD-6): these key names are confirmed, with the field `name` on `MetadataNodeInput` of the GraphQL contract.

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

## What the Python SDK sends

Decisions of the implementation (tasks T139 and T140):

- The SDK sends the keys inside the `data` input of the upsert mutation of each node, as `node_metadata`.
- A plain name goes as `{name: "dc-emea"}`. The typed form goes as `{kind: "CoreAccount", name: "jdoe"}`. Infrahub resolves both.
  - `MetadataNodeInput` of the GraphQL contract got the field `name` for this: `name: String`, next to `id`, `hfid` and `kind`.
  - With a kind, the name is the HFID of the node. This works for a kind whose HFID has one value.
  - Without a kind, the name is the name of an account group. Infrahub refuses it when an account has the same name.
- The owners of a field go as `node_metadata.field_owners`. On a profile or an object template, they go as `node_metadata.target_field_owners`.
- A field that has only `owners` sends no value and no peers.
- The SDK refuses these files before the load:
  - `target_owners` on a kind that is not a profile or an object template
  - an unknown key under `node_metadata`
  - an owner that is not a name or `{kind, name}`
  - `owners` next to the peers of a relationship
- The SDK does not check `node_metadata` of the peers that an object declares inline for a relationship whose mutation takes the peer fields. This case is not supported.

## Refusals

- An owner that is not valid refuses the whole node, with the errors of the GraphQL contract.
- When the change check refuses a node, the load stops at that node (FR-045).
