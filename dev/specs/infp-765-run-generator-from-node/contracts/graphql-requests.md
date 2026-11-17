# Contract: GraphQL Requests

The feature uses existing GraphQL fields only. The GraphQL schema does not change. All requests run on the branch the user is viewing; the read requests also use the time-travel date, if one is set.

## 1. Generator definitions and node membership (new static query)

```graphql
query GetGeneratorDefinitionsForNode($nodeId: ID!) {
  CoreGeneratorDefinition {
    edges {
      node {
        id
        display_label
        targets {
          node {
            id
            display_label
            members(ids: [$nodeId]) {
              count
            }
          }
        }
      }
    }
  }
}
```

- `members(ids: [$nodeId]).count` is 1 when the node is a direct member of the target group, 0 otherwise. Descendants are excluded because `include_descendants` is not set.
- No limit is set; list queries have no default page size, so all definitions return.
- Requires `view` on `CoreGeneratorDefinition` and on every kind that uses `CoreGroup`. A denial fails the request; the section then stays hidden.
- Errors are not shown to the user (`processErrorMessage: () => {}`).

## 2. Members of the node's kind per target group (new dynamic query)

Built with `jsonToGraphQLQuery`, one aliased field per distinct target group id from request 1. Example for a node of kind `NetworkFabric` and two target groups:

```graphql
query GetTargetGroupKindCounts {
  group0: NetworkFabric(member_of_groups__ids: ["<group 0 id>"]) {
    count
  }
  group1: NetworkFabric(member_of_groups__ids: ["<group 1 id>"]) {
    count
  }
}
```

- The node's concrete kind comes from its `__typename`.
- Aliases map back to group ids by position; the response is turned into a map from group id to count.
- `count` is the total of direct members of that kind in the group, independent of any limit. Only `count` is selected, so no nodes are fetched and no `view` permission on the kind is required.
- The request is skipped when request 1 returns no definition.
- Errors are not shown to the user (`processErrorMessage: () => {}`).

## 3. Start the run (existing mutation, unchanged)

```graphql
mutation CoreGeneratorDefinitionRun($generatorId: String!, $waitUntilCompletion: Boolean, $targetNodeIds: [String!]) {
  CoreGeneratorDefinitionRun(
    wait_until_completion: $waitUntilCompletion
    data: { id: $generatorId, nodes: $targetNodeIds }
  ) {
    task {
      id
    }
  }
}
```

- Called through the existing `runGeneratorFromApi` with `waitUntilCompletion: false`, which returns the task id, and `targetNodeIds: [<node id>]`.
- `RunGeneratorFromApiParams` gains an optional `processErrorMessage`, passed through to the request context. The section passes `() => {}` and shows its own error message. Callers that omit it keep the default error toast.
- The server refuses the run for anonymous users, and on the default branch for users without `edit_default_branch`.
- A node id that is not a direct member of the target group is skipped by the server without an error. This is unchanged and out of scope.
