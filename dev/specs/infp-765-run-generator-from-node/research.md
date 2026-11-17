# Research: Run a Generator for a Node from the Node's Page

Phase 0 output for [plan.md](plan.md). Each entry records the decision, why, and what else was weighed.

## R1. Finding the generator definitions that target a node

**Decision**: Two read requests with existing GraphQL fields.

1. List every `CoreGeneratorDefinition` with its target group and `targets { node { members(ids: [<node id>]) { count } } }`. The count is 1 when the node is a direct member, 0 otherwise.
2. For each distinct target group, count the members of the node's kind with `<Kind>(member_of_groups__ids: ["<group id>"]) { count }`, one aliased field per group in a single request.

A definition targets the node when request 2 returns a count above 0 for its group. The item is enabled when request 1 returns a count above 0.

**Rationale**: Verified against the resolvers.

- `backend/infrahub/graphql/resolvers/resolver.py::default_paginated_list_resolver` passes the same filter dict to the list and to `NodeManager.count`, which counts without limit or offset. When only `count` is selected, no nodes are fetched.
- `member_of_groups__ids` resolves through `RelationshipSchema.get_query_filter` as a single hop to the group: direct members on the queried branch, not members of child groups.
- `backend/infrahub/graphql/resolvers/many_relationship.py::ManyRelationshipResolver` applies the `ids` filter to the nested count (`members__ids`), returns without fetching peers when only `count` is selected, and includes descendants only when `include_descendants` is true.
- Aliased fields resolve independently, each with its own arguments.
- List queries have no default or maximum page size, so the definition list is not truncated.

The backend flow that runs generators also uses direct members only (`backend/infrahub/generators/tasks.py::request_generator_definition_run`), so the enabled state matches what a run does.

**Alternatives considered**:

- **The node's `member_of_groups` plus `CoreGeneratorDefinition(targets__ids: ...)`**: gives membership only. It cannot tell "a node of a targeted kind outside the group" (disabled) from "a node of an unrelated kind" (hidden).
- **`CoreGraphQLQuery.models` of the definition's query**: lists every kind the query reads, including nested peers such as templates, so unrelated kinds would show a disabled item.
- **A declared target kind on `CoreGeneratorDefinition`**: exact and works for empty groups, but it is a core schema change plus an SDK change. Rejected during the grilling session.
- **`CoreGeneratorInstance(object__ids: ...)`**: misses definitions that never ran for the node.
- **A new resolver field**: not needed; existing filters answer the question.

## R2. When the data is fetched

**Decision**: When the Actions menu opens. The section lives inside the menu popover, which mounts its content only while open.

**Rationale**: The Actions menu is opened on a small share of node page views; fetching at page load would add two requests to every node page. The query keys sit under `objectQueryKeys.all`, which every group add or remove, object edit and the header refresh button already invalidate. An invalidated query that is not mounted is marked stale and refetches on the next open, so US3 scenario 2 (add the node to the group, reopen the menu, the item is available) works without extra wiring.

**Alternatives considered**: fetching at page load in `ObjectDetailsMenu` makes the section appear without delay on first open, at the cost of two requests on every node page view. Rejected for now; revisit if the first-open delay is noticeable.

## R3. Who may view the section

**Decision**: A pure rule, `canRunGenerators({ isAuthenticated, isDefaultBranch, hasEditDefaultBranch })`, returns true when the user is signed in and either the branch is not the default branch or the user holds `edit_default_branch`.

- `isAuthenticated` comes from `useAuth()`.
- `isDefaultBranch` comes from `useCurrentBranch().currentBranch.is_default`, never from comparing the name with `main` (`dev/knowledge/frontend/branches.md`).
- `hasEditDefaultBranch` comes from `useHasGlobalPermission`, which resolves the action or `super_admin`.

`release-1.12` already defines the `EDIT_DEFAULT_BRANCH` constant in `entities/permission/domain/model/permission.ts`. One small addition is needed:

- An optional `config?: QueryConfig<...>` parameter on `useHasGlobalPermission`, following the documented hook shape `useGetX(params, config?)`, so the permission query runs only when `isAuthenticated && isDefaultBranch`.

**Rationale**: The rule mirrors the backend: anonymous users are refused every mutation, and `DefaultBranchPermissionChecker` requires `edit_default_branch` for mutations on the default branch. `CoreGeneratorDefinitionRun` is not exempt, and object permissions do not apply to it. Today `useHasGlobalPermission` has no `enabled` option and runs for anonymous users too; gating it avoids a pointless request on every menu open.

**Alternatives considered**:

- **Split components**, where an inner component calls `useHasGlobalPermission` only when rendered: works without touching the shared hook, but spreads one condition over three components and leaves no pure rule to unit-test.
- **Always query the permission**: an extra request for anonymous users and on non-default branches, where the answer is not used.

## R4. Error handling

**Decision**:

- **Read requests**: pass `processErrorMessage: () => {}`. On error the section renders nothing; the client still logs the error.
- **Run request**: add an optional `processErrorMessage` to `RunGeneratorFromApiParams` and pass it through to the request context. The section passes `() => {}` and shows its own error toast from the mutation's `onError`, with the thrown message.
- **Where the toasts are raised**: as `useRunGeneratorMutation` hook options, not `mutate` options. Selecting a menu item closes the menu and unmounts the section before the request returns, and TanStack Query skips `mutate`-level callbacks after the component unmounts. The hook gains an optional `config`, as `useReimportLastCommitMutation` has.

**Rationale**: `shared/api/graphql/error-handling.ts::handleGraphQLErrors` toasts most errors, but skips `PERMISSION_DENIED` because route guards handle it. A run refused for a missing permission would otherwise fail silently, which breaks FR-007. Handling the toast in the section, with the default toast suppressed, shows each error once. Passing `processErrorMessage` when the caller shows its own toast is the documented convention for `*-from-api` files. The parameter is optional, so the existing Run buttons keep their behavior.

A failing read is not reported: the most likely cause is a role that denies `view` on a group kind, which fails the whole definitions query (`ObjectPermissionChecker` checks per kind and never filters rows). Hiding the section is the right outcome there.

**Alternatives considered**: reusing the global toast id to deduplicate couples the section to an internal default; leaving the global toast alone misses permission errors.

## R5. Link in the success message

**Decision**: Link to `getTaskDetailsUrl(taskId)`, the global task page.

**Rationale**: The node-scoped `tasks/:taskId` route does not exist under the IPAM routes, and the menu is shared with IP prefix and IP address pages. The returned task is the parent `request-generator-definition-run` flow; the per-node child run is also tagged with the node, so it appears under the node's Tasks link.

## R6. Request results and permissions

- **Anonymous read access**: the anonymous role holds `*:*:view:ALLOW_ALL`, so the read requests succeed. The section is hidden anyway by R3.
- **Definitions query**: needs `view` on `CoreGeneratorDefinition` and on every kind that uses `CoreGroup`. A denial fails the whole query (R4).
- **Kind-count query**: selects only `count`, outside `edges/node`, so it requires no `view` on the node's kind.

## R7. Tests

- **Frontend unit tests (Vitest)** for the two pure rules, co-located as `*.test.ts`, with the `tests/fake/` factories.
- **Frontend component test** for the menu section, co-located as `*.test.tsx`.
  - Render inside `<Menu aria-label>` as `entities/repository/ui/repository-menu-section.test.tsx` does.
  - Mock the use case and the mutation hook with `vi.mock`; there is no MSW.
  - Wrap in an `AuthContext` value for signed-in cases; the test `render` has no auth provider, so tests are anonymous by default.
  - Hover disabled items with `initPointerTracking` for the tooltip.
- **E2E test** in `tests/e2e/objects/test_object_details_generators.py`, marked `shard_branches_repo`, using `demo_edge_repo`.
  - Only `update_upstream_interfaces_description` has a populated target group: `upstream_interfaces`, with the `InfraInterfaceL3` nodes whose role is `upstream`. The circuit groups (`provisioning_circuits` and others) are empty.
  - Enabled: atl1-edge1 Ethernet5.
  - Disabled: atl1-edge1 Ethernet7 (role `spare`). Add it to the group on the branch, then the item is enabled.
  - Hidden by kind: a `LocationSite` or an `InfraDevice`. An `InfraCircuit` covers the empty-group case.
  - Hidden by permission: `read_only_page` (jbauer, no `edit_default_branch`) on the default branch; the same account views the section on a branch.
  - Hidden when signed out: `page`.
  - Run checks: read the task id from the "View task" link, poll `InfrahubTask` state with `helpers.Deadline` until `COMPLETED` (pattern: `tests/e2e/repository/test_repository_check_remote.py`), then assert one `CoreGeneratorInstance` for the definition on the branch, whose `object` is Ethernet5. Run generators only on throwaway branches.
- **No backend test.** No existing test passes `nodes` through the mutation; the flow-level filter is covered by `backend/tests/component/proposed_change/test_generator_definition_run_member_failure.py`. The E2E run test covers the mutation argument: `upstream_interfaces` has other members, and the test asserts that the only generator instance for the definition points at Ethernet5.

## R8. Code generation

The static definitions query is typed by gql.tada. `pnpm codegen:graphql` updates `frontend/app/src/shared/api/graphql/generated/graphql-cache.d.ts`, which is committed; CI fails when it is stale. `graphql-env.d.ts` does not change, because the backend schema does not change. The aliased kind-count query is built at run time with `jsonToGraphQLQuery` and is untyped, as `entities/repository/api/get-repository-sync-counts-from-api.ts` is.
