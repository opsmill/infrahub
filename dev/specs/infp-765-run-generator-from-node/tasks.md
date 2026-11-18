---
description: "Task list for running a generator for a node from the node's page"
---

# Tasks: Run a Generator for a Node from the Node's Page

**Input**: Design documents from `specs/infp-765-run-generator-from-node/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. The constitution requires an E2E test for user-facing features. The plan adds unit tests and a component test.

**Organization**: Tasks are grouped by user story so each story can be built and checked on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: The user story the task belongs to (US1, US2, US3)

## Path conventions

- Frontend source: `frontend/app/src/`. Frontend test helpers: `frontend/app/tests/` (`components/render.tsx`, `components/utils.ts`, `fake/*.ts`).
- E2E tests: `tests/e2e/`.
- Frontend rules to follow:
  - `dev/knowledge/frontend/entities-structure.md` (api/domain/ui layers)
  - `dev/guidelines/frontend/naming-conventions.md`
  - `dev/guides/frontend/writing-unit-tests.md` and `writing-component-tests.md`: GIVEN/WHEN/THEN, co-located `*.test.ts(x)`, `vi.mock`, no MSW
- Comments and docstrings follow `dev/guidelines/code-doc-style.md`.

---

## Phase 1: Setup

**Purpose**: A working toolchain and a green baseline.

- [X] T001 Make `pnpm` available, then run `cd frontend/app && pnpm install`. `pnpm` is missing in the current environment; ask the user before installing anything globally.
- [X] T002 Record the baseline:
  - `cd frontend/app && pnpm test src/entities/generators src/entities/permission src/entities/nodes/object`
  - `PYTHONPATH=python_sdk TESTCONTAINERS_RYUK_DISABLED=true uv run pytest backend/tests/functional/generator/test_mutation_generator.py`

  Note any failures that exist before the change.

---

## Phase 2: Foundational (data layer shared by all stories)

**Purpose**: Read which generator definitions target a node, and whether the node is a member of each target group. Contracts 1 and 2 in [contracts/graphql-requests.md](contracts/graphql-requests.md). The model is in [data-model.md](data-model.md).

**⚠️ CRITICAL**: The user story phases need this data layer.

- [X] T003 [P] Create `NodeGeneratorDefinition` (`id`, `label`, `groupId`, `groupLabel`, `isMember`) in `frontend/app/src/entities/generators/domain/model/node-generator-definition.ts`.
- [X] T004 [P] Create `getGeneratorDefinitionsForNodeFromApi` in `frontend/app/src/entities/generators/api/get-generator-definitions-for-node-from-api.ts`.
  - A static `graphql(...)` document named `GetGeneratorDefinitionsForNode($nodeId: ID!)`, exactly as in contract 1.
  - Params: `VariablesOf<typeof doc> & ContextParams`.
  - Call `graphqlClient.query` with `context: { branch: branchName, date: atDate, processErrorMessage: () => {} }`.
  - Pattern: `frontend/app/src/entities/permission/api/get-global-permissions-from-api.ts`.
- [X] T005 [P] Create `getTargetGroupKindCountsFromApi({ nodeKind, groupIds, branchName, atDate })` in `frontend/app/src/entities/generators/api/get-target-group-kind-counts-from-api.ts`.
  - Build the query with `jsonToGraphQLQuery`, `__name: "GetTargetGroupKindCounts"`.
  - Add one field per group: alias `group${index}` with `__aliasFor: nodeKind`, `__args: { member_of_groups__ids: [groupId] }` and `count: true`.
  - Pass the same context as T004, including `processErrorMessage: () => {}`.
  - Pattern: `frontend/app/src/entities/repository/api/get-repository-sync-counts-from-api.ts`.
- [X] T006 Run `cd frontend/app && pnpm codegen:graphql` and keep the updated `frontend/app/src/shared/api/graphql/generated/graphql-cache.d.ts`. Depends on T004.
- [X] T007 [P] Write unit tests in `frontend/app/src/entities/generators/domain/rules/select-node-generator-definitions.test.ts`. Cases:
  - no definitions → `[]`
  - a definition whose group count is 0 → not listed
  - a definition whose group count is missing from the map → not listed
  - group count > 0 with member count 1 → `isMember: true`
  - group count > 0 with member count 0 → `isMember: false`
  - two definitions sharing one group → two entries, in input order
  - a definition without a target group → skipped
- [X] T008 Implement `selectNodeGeneratorDefinitions({ definitions, kindCountByGroupId })` in `frontend/app/src/entities/generators/domain/rules/select-node-generator-definitions.ts`.
  - A pure function returning `NodeGeneratorDefinition[]` that passes T007.
  - It takes the definitions as returned by T004, typed with the gql.tada `ResultOf`, and a `Map<string, number>`.
  - Depends on T003 and T006.
- [X] T009 Implement the use case `getNodeGeneratorDefinitions` in `frontend/app/src/entities/generators/domain/use-cases/get-node-generator-definitions.ts`.
  - Export `GetNodeGeneratorDefinitionsParams = { nodeId: string; nodeKind: string } & ContextParams` and `GetNodeGeneratorDefinitionsResult = NodeGeneratorDefinition[]`, in the `export type X = (p) => Promise<...>; export const x: X = async ...` shape.
  - Steps:
    1. Call T004.
    2. Collect the distinct target group ids. Return `[]` when there are none, so T005 is skipped.
    3. Call T005.
    4. Turn the aliased response into a `Map` from group id to count with a type guard (no `as`). Use the alias index to find the group id.
    5. Return the result of the T008 rule.
  - Depends on T004, T005 and T008.
- [X] T010 [P] Create `generatorsQueryKeys` in `frontend/app/src/entities/generators/ui/queries/generator.query-keys.ts`.
  - `all(context)` is `[...objectQueryKeys.allWithContext(context), "generators"] as const`.
  - `nodeDefinitions(params: GetNodeGeneratorDefinitionsParams)` adds `"node-definitions", nodeKind, nodeId`.
  - Pattern: `frontend/app/src/entities/nodes/object-file/ui/queries/object-file.query-keys.ts`.
- [X] T011 Create `getNodeGeneratorDefinitionsQueryOptions(params)` and `useGetNodeGeneratorDefinitions(params: Omit<GetNodeGeneratorDefinitionsParams, keyof ContextParams>, config?: QueryConfig<typeof getNodeGeneratorDefinitionsQueryOptions>)` in `frontend/app/src/entities/generators/ui/queries/get-node-generator-definitions.query.ts`.
  - Read `useCurrentBranch()` and `datetimeAtom`, and spread `config` last.
  - Pattern: `frontend/app/src/entities/nodes/object/ui/queries/get-object.query.ts`.
  - Depends on T009 and T010.

**Checkpoint**: `pnpm test src/entities/generators` passes. The hook returns the targeted definitions for a node.

---

## Phase 3: User Story 1 - Start a generator for a node from its page (Priority: P1) 🎯 MVP

**Goal**: The node Actions menu has a "Generators" section with one "Run <definition>" item per targeted definition. Selecting one starts a run for this node only and shows one success or error toast. Contract: [contracts/generators-menu-section.md](contracts/generators-menu-section.md).

**Independent Test**: On a branch, open the page of a member of a target group, select the item, and verify that one run starts for that node only and that the message links to the task.

### Tests for User Story 1

- [X] T012 [US1] Dropped: no backend functional test is added. The E2E run test in T017 asserts that a run started from the menu creates one generator instance, for that node only.
- [X] T013 [P] [US1] Write component tests in `frontend/app/src/entities/generators/ui/node-generators-menu-section.test.tsx`.
  - Setup:
    - Render inside `<Menu aria-label="Node actions">`, as `frontend/app/src/entities/repository/ui/repository-menu-section.test.tsx` does.
    - Wrap in `<AuthContext value={{ isAuthenticated: true, accessToken: "t", setToken: () => {}, user: { id: "u" } }}>` (pattern: `frontend/app/src/entities/user-profile/ui/account-menu.test.tsx`).
    - Keep the default `generateBranch()`, which is not the default branch.
    - `vi.mock` the use cases `@/entities/generators/domain/use-cases/get-node-generator-definitions` and `@/entities/generators/domain/use-cases/run-generator`, so the real query and mutation hooks run (pattern: `frontend/app/src/entities/user-profile/ui/account-menu.test.tsx`).
  - Cases, each with one GIVEN/WHEN/THEN:
    - (a) two member definitions → section title "Generators" and items "Run gen-a" and "Run gen-b"
    - (b) selecting "Run gen-a" calls `mutate` with `{ generatorId: "gen-a-id", targetNodeIds: ["node-1"], processErrorMessage: expect.any(Function) }`
    - (c) on success with task id `t-1`, the toast reads "Generator gen-a started for Fabric-E." and its "View task" link points to `/tasks/t-1`
    - (d) on error "boom", the toast reads "Could not start generator gen-a: boom"
    - (e) while gen-a's request is pending, "Run gen-a" has `aria-disabled="true"` and "Run gen-b" does not

### Implementation for User Story 1

- [X] T014 [US1] Add an optional `processErrorMessage?: (message: string) => void` to `RunGeneratorFromApiParams` in `frontend/app/src/entities/generators/api/run-generator-from-api.ts`, and pass it in `context` next to `branch`. Existing callers that omit it keep the default error toast. Also give `useRunGeneratorMutation` (`frontend/app/src/entities/generators/ui/queries/run-generator.mutation.ts`) an optional `config?: Omit<MutationConfig<typeof runGenerator>, "mutationFn">`, spread before its own `onSuccess`, which keeps invalidating `tasksQueryKeys.all` and then calls `config.onSuccess` (pattern: `frontend/app/src/entities/repository/ui/queries/reimport-last-commit.mutation.ts`). Existing callers pass nothing.
- [X] T015 [US1] Create `NodeGeneratorsMenuSection({ nodeId, nodeKind, nodeLabel })` in `frontend/app/src/entities/generators/ui/node-generators-menu-section.tsx`.
  - Reads `useGetNodeGeneratorDefinitions({ nodeId, nodeKind })`.
  - Renders `null` unless data is present and non-empty.
  - Otherwise renders `<MenuSection title="Generators">` with one `MenuItem` per definition: lucide `PlayIcon` plus `Run {label}`.
  - `onAction` calls `useRunGeneratorMutation().mutate({ generatorId, targetNodeIds: [nodeId], processErrorMessage: () => {} }, { onSuccess, onError })`.
  - Tracks the id of the definition being started in state, so only that item is disabled while pending.
  - Success toast: `<Alert type={ALERT_TYPES.SUCCESS}>` with "Generator {label} started for {nodeLabel}." and a "View task" `Link` to `getTaskDetailsUrl(taskId)`.
  - Error toast: `<Alert type={ALERT_TYPES.ERROR}>` with "Could not start generator {label}: {error.message}".
  - Pattern: `frontend/app/src/entities/repository/ui/repository-menu-section.tsx`.
  - Depends on T011 and T014.
- [X] T016 [US1] Render `<NodeGeneratorsMenuSection nodeId={objectData.id} nodeKind={objectData.__typename} nodeLabel={nodeLabel} />` in `frontend/app/src/entities/nodes/object/ui/object-details/object-details-menu.tsx::ObjectDetailsMenu`, after the `RepositoryMenuSection` block and before `<MenuSection title="Manage">`. Depends on T015.
- [X] T017 [US1] Create `tests/e2e/objects/test_object_details_generators.py`.
  - Module setup:
    - `pytestmark = pytest.mark.shard_branches_repo`
    - a test class using `demo_edge_repo`
    - a function-scoped throwaway branch fixture with `branch_api` and `generate_random_branch_name` (pattern: `tests/e2e/objects/test_object_details.py::TestObjectDetails.branch`)
    - module helpers `read_task_state` and the task-id parsing (pattern: `tests/e2e/repository/test_repository_check_remote.py`)
  - Add `test_run_generator_from_member_page` (admin, on the branch):
    1. Open atl1-edge1 Ethernet5 (`InfraInterfaceL3`, found with the SDK by device and `name__value="Ethernet5"`) at `/objects/InfraInterfaceL3/<id>?branch=<branch>`.
    2. Click `object-details-menu`, then the menuitem "Run update_upstream_interfaces_description".
    3. Expect the toast "Generator update_upstream_interfaces_description started for Ethernet5." and read the task id from the "View task" link.
    4. Poll the task state with `helpers.Deadline` until `COMPLETED`.
    5. Assert exactly one `CoreGeneratorInstance` with `definition__ids=[<definition id>]` on the branch, whose `object` is Ethernet5.

**Checkpoint**: T013 and T017 pass. US1 works on its own on a non-default branch.

---

## Phase 4: User Story 2 - View generators only where they apply (Priority: P2)

**Goal**: No section for nodes of kinds no target group contains. No section for users who are not signed in, or who lack `edit_default_branch` on the default branch. No data request when the user may not run generators.

**Independent Test**: A location page shows no section. On the default branch, a user without `edit_default_branch` sees no section on a target node. A signed-out user sees no section.

### Tests for User Story 2

- [X] T018 [P] [US2] Write unit tests in `frontend/app/src/entities/generators/domain/rules/can-run-generators.test.ts`:
  - not signed in → false (on both branch types)
  - default branch with `hasEditDefaultBranch: true` → true
  - default branch with `false` → false
  - default branch with `undefined` (unresolved) → false
  - other branch with `false` → true
- [X] T019 [P] [US2] Add component tests to `frontend/app/src/entities/generators/ui/node-generators-menu-section.test.tsx`. Also `vi.mock` the use case `@/entities/permission/domain/use-cases/has-global-permission`.
  - (a) signed-out `AuthContext` → no "Generators" text, and `getNodeGeneratorDefinitions` is never called
  - (b) signed in, current branch `generateBranch({ is_default: true, name: "trunk" })` (not named `main`, per the component-test guide), permission `false` → no section
  - (c) same with permission `true` → section shown
  - (d) signed in, non-default branch → `hasGlobalPermission` is never called, and the section is shown
  - (e) hook returns `[]` → no section
- [X] T020 [P] [US2] Add to `tests/e2e/objects/test_object_details_generators.py`:
  - `test_section_hidden_for_untargeted_kind`: admin on the branch. The `LocationSite` atl1 page and an `InfraCircuit` page each show no "Generators" text after the Actions menu opens (`to_have_count(0)`).
  - `test_section_hidden_without_edit_default_branch`: `read_only_page` (jbauer) on the default branch, Ethernet5 page → no section.
  - `test_section_shown_on_branch_without_edit_default_branch`: jbauer on the throwaway branch → section shown.
  - `test_section_hidden_when_signed_out`: `page` fixture, Ethernet5 on the default branch → no section.

### Implementation for User Story 2

- [X] T021 [P] [US2] Use the existing `EDIT_DEFAULT_BRANCH` constant in `frontend/app/src/entities/permission/domain/model/permission.ts`. `release-1.12` already defines it, so this change adds nothing to that file.
- [X] T022 [P] [US2] Add an optional second parameter `config?: QueryConfig<typeof hasGlobalPermissionQueryOptions>` to `useHasGlobalPermission` in `frontend/app/src/entities/permission/ui/queries/has-global-permission.query.ts`, spread after the query options. Existing callers stay unchanged.
- [X] T023 [P] [US2] Implement `canRunGenerators({ isAuthenticated, isDefaultBranch, hasEditDefaultBranch })` in `frontend/app/src/entities/generators/domain/rules/can-run-generators.ts`.
  - Returns `isAuthenticated && (!isDefaultBranch || hasEditDefaultBranch === true)`.
  - `hasEditDefaultBranch` is `boolean | undefined`.
  - Passes T018.
- [X] T024 [US2] Gate the section in `frontend/app/src/entities/generators/ui/node-generators-menu-section.tsx::NodeGeneratorsMenuSection`.
  1. Read `useAuth().isAuthenticated` and `!!useCurrentBranch().currentBranch.is_default`.
  2. Call `useHasGlobalPermission(EDIT_DEFAULT_BRANCH, { enabled: isAuthenticated && isDefaultBranch })`.
  3. Compute `canRunGenerators`.
  4. Pass `{ enabled: canRun }` to `useGetNodeGeneratorDefinitions`.
  5. Render `null` when `canRun` is false.

  Passes T019. Depends on T015, T021, T022 and T023.

**Checkpoint**: T018, T019 and T020 pass. US1 tests still pass.

---

## Phase 5: User Story 3 - Understand why a generator cannot run for a node (Priority: P3)

**Goal**: For a node of a targeted kind that is not a direct member of the target group, the item is disabled and its tooltip names the group. After the node joins the group, reopening the menu shows the item enabled.

**Independent Test**: Create or pick a node of a targeted kind outside the group, check the disabled item and its tooltip, add the node to the group, and check that the item is enabled.

### Tests for User Story 3

- [X] T025 [P] [US3] Add component tests to `frontend/app/src/entities/generators/ui/node-generators-menu-section.test.tsx`:
  - (a) a definition with `isMember: false` → "Run gen-a" has `aria-disabled="true"`. Hovering it (after `initPointerTracking(component.locator)` from `frontend/app/tests/components/utils.ts`) shows a tooltip "Fabric-F is not a member of the target group fabrics". Move the pointer away afterwards.
  - (b) a definition with `isMember: true` → the item is not disabled, and hovering shows no tooltip.
- [X] T026 [P] [US3] Add `test_item_disabled_until_node_joins_target_group` to `tests/e2e/objects/test_object_details_generators.py` (admin, on the throwaway branch):
  1. Open atl1-edge1 Ethernet7. After opening the menu, "Run update_upstream_interfaces_description" has `aria-disabled="true"`.
  2. Hovering shows a tooltip with the text "Ethernet7 is not a member of the target group upstream_interfaces" (pattern: `tests/e2e/branches/test_merged_branch_permissions.py`).
  3. Close the menu and add Ethernet7 to `upstream_interfaces` on the branch with the SDK (`client.get(kind="CoreStandardGroup", name__value="upstream_interfaces", branch=...)`, then add the member and save).
  4. Reload the page and reopen the menu: the item no longer has `aria-disabled="true"`.

### Implementation for User Story 3

- [X] T027 [US3] In `frontend/app/src/entities/generators/ui/node-generators-menu-section.tsx::NodeGeneratorsMenuSection`, set:
  - `isDisabled={!definition.isMember || startingId === definition.id}`
  - `tooltip={definition.isMember ? undefined : \`${nodeLabel} is not a member of the target group ${definition.groupLabel}\`}`

  `MenuItem` shows the tooltip only while disabled, so the pending state shows none. Passes T025.

**Checkpoint**: All story tests pass.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T028 [P] In `docs/docs/generators/overview.mdx`, under "Manually from the UI", add after the existing sentence: "You can also run a Generator for one target from that target's page: open the Actions menu and select the Generator in the Generators section." Then run `uv run invoke docs.lint`.
- [X] T029 [P] Add a towncrier `added` fragment with the `creating-changelog-entries` skill. Fragments in `changelog/` use the `+<slug>.added.md` naming (for example `changelog/+run-generator-from-node.added.md`). The text says that a node's Actions menu now lists the generators that target the node and runs one for that node only.
- [X] T030 Run the frontend CI gate:
  - `cd frontend && pnpm exec biome ci .`
  - `cd frontend/app && pnpm knip && pnpm exec betterer ci && pnpm test`

  Fix every finding. `knip` flags unused exports, so export only what is imported.
- [X] T031 Verify the generated files: `cd frontend/app && pnpm codegen:graphql && git diff --exit-code -- src/shared/api/graphql/generated/`. Expect no difference once T006's output is committed.
- [X] T032 Run the [quickstart.md](quickstart.md) validation: the E2E file with `uv run pytest -c tests/e2e/pytest.ini tests/e2e/objects/test_object_details_generators.py -s --pdb`.
- [X] T033 Run `/pre-ci` from the repository root and fix what it reports.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: none.
- **Foundational (Phase 2)**: needs Setup. Blocks all stories.
- **US1 (Phase 3)**: needs Foundational.
- **US2 (Phase 4)**: needs Foundational. Its gating task T024 edits the component created in T015, so T024 follows T015.
- **US3 (Phase 5)**: needs Foundational. T027 edits the component created in T015.
- **Polish (Phase 6)**: needs the stories that ship.

### Within phases

- T006 after T004. T008 after T003, T006 and T007. T009 after T004, T005 and T008. T011 after T009 and T010.
- T015 after T011 and T014. T016 after T015.
- T024 after T015 and T021–T023. T027 after T015.
- Write each story's tests first and watch them fail.

### Parallel opportunities

- Phase 2: T003, T004, T005, T007 and T010 together.
- US1: T013 alongside T014.
- US2: T018, T019 and T020 together; T021, T022 and T023 together.
- US3: T025 and T026 together.
- Polish: T028 and T029 together.
- The E2E file is shared by T017, T020 and T026. Those tasks are marked [P] only against tasks in other files; edit that file one task at a time.

## Parallel Example: User Story 2

```bash
# Tests together:
Task: "Unit tests for canRunGenerators in frontend/app/src/entities/generators/domain/rules/can-run-generators.test.ts"
Task: "Visibility component tests in frontend/app/src/entities/generators/ui/node-generators-menu-section.test.tsx"

# Implementation building blocks together:
Task: "Optional config on useHasGlobalPermission in frontend/app/src/entities/permission/ui/queries/has-global-permission.query.ts"
Task: "canRunGenerators rule in frontend/app/src/entities/generators/domain/rules/can-run-generators.ts"
```

## Implementation Strategy

### MVP first (User Story 1)

1. Phase 1 and Phase 2.
2. Phase 3 (US1). Validate on a non-default branch: the item runs the generator for the node only.
3. Do not release US1 alone. Without US2, users who lack `edit_default_branch` see the section on the default branch, and the server refuses their run. Without US3, a non-member item is enabled, and the run reports success while running nothing.

### Incremental delivery

1. Foundation, then US1, then US2, then US3, each followed by its checkpoint tests.
2. The feature ships as one change once all three stories and Phase 6 are done, because every story is in scope for the first implementation.

## Notes

- Cite code by module and symbol, never by line number (`dev/guidelines/documentation.md`).
- Do not commit until the user asks (`/speckit-git-commit` or the `commit` skill).
