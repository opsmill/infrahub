---

description: "Task list for the number pool details header"
---

# Tasks: Number pool details header

**Input**: Design documents from `dev/specs/ifc-3364-number-pool-header/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/number-pool-header.md](contracts/number-pool-header.md), [quickstart.md](quickstart.md)

**Tests**: included. Constitution principle IV requires tests for every feature and an end-to-end test for user-facing features, and research.md R11 lists them. Within the user story phase, write each test before the code it covers and confirm it fails first.

**Organization**: the spec has one user story (US1). Phases 1 and 2 hold the type, the vocabulary and the refactors that the story builds on. Phase 3 delivers the story. Phase 4 covers the changelog, generated files and the quality gates.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1)
- Paths are relative to the repository root. `src/` means `frontend/app/src/`.

## Conventions every task follows

- **Before starting**: read `frontend/app/AGENTS.md`, `dev/knowledge/frontend/entities-structure.md` and `dev/guidelines/code-doc-style.md`.
- **React and libraries**: write `import React from "react"` and call `React.useState` and similar. Never use named imports from `"react"`. Import remeda as `import * as R from "remeda"`. Don't use manual `useMemo` or `useCallback` (the React Compiler is on). Use lucide-react icons, sized with `className`.
- **Types**: no `any`, no non-null `!`, no `as` casts outside tests.
- **Tests**: each test has exactly one `// GIVEN`, one `// WHEN` and one `// THEN` marker. Render with `frontend/app/tests/components/render.tsx`. Assert with `await expect.element(...)`. Prefer `getByRole`.
- **Comments**: only for a non-obvious reason, one sentence. Don't mention ticket IDs or spec vocabulary in code or test names.
- **Citations**: code sites are named by `file::symbol`, never by line number.

---

## Phase 1: Setup (shared vocabulary and type)

**Purpose**: the domain vocabulary and the type that every later task imports.

- [X] T001 [P] Add `NUMBER_POOL_TYPE_SCHEMA = "Schema"`, `NUMBER_POOL_TYPE_USER = "User"` and the `NumberPoolType` union next to `NUMBER_POOL_KIND` in `src/entities/resource-manager/domain/model/pool.ts` (research.md R6).
- [X] T002 [P] Add the `NumberPoolData` interface to `src/entities/resource-manager/domain/model/number-pool.ts`, next to the existing `NumberPool` interface. It extends `NodeCore` and keeps the API field names with `NodeAttribute<T>` values, exactly as in data-model.md: `name`, `description`, `pool_type`, `node`, `node_attribute`, `allocation_scope`.

---

## Phase 2: Foundational (refactors the story builds on)

**Purpose**: changes to shared code that keep existing behaviour and that the number pool page needs. Each task leaves the app working.

**Required order**: finish this phase before Phase 3.

- [X] T006 [P] Add three URL builders to `src/entities/nodes/object/ui/routing/object-urls.ts` (research.md R4; contract "URL builders (moved)"). Move their bodies from `src/entities/nodes/object/ui/object-details/object-details-menu.tsx::ObjectDetailsMenu`, which builds them inline today:
  - `getObjectTasksUrl(objectId: string): string`, the `/tasks` URL filtered on `node__value`.
  - `getObjectGraphqlSandboxUrl(objectKind: string, objectId: string): string`, the `/graphql` URL whose query selects `nodeCoreFragment` for `ids: [objectId]`.
  - `getDocumentationUrl(documentation: string): string`, the documentation URL when it starts with `http`, otherwise `INFRAHUB_DOC_LOCAL` followed by the documentation path.

  Add unit tests in `src/entities/nodes/object/ui/routing/object-urls.test.ts` if the file exists, otherwise create it, with one test per builder.
- [X] T007 Replace the inline builders with the T006 functions in `src/entities/nodes/object/ui/object-details/object-details-menu.tsx::ObjectDetailsMenu` and `src/entities/artifacts/ui/artifact-details-menu.tsx`. The artifact sandbox query now also selects `__typename` through `nodeCoreFragment`. That is the only change in behaviour, and it is harmless.
- [X] T008 Move the body of `src/pages/resource-manager/resource-pool-details.tsx::ResourcePoolContent` into a new file, `src/pages/resource-manager/resource-pool-details-body.tsx`, exporting `ResourcePoolDetailsBody({ poolId, schema, permission })` (research.md R10). No behaviour changes:
  - **What moves**: the `<div className="flex items-start overflow-hidden p-2">` block, which holds the side `Card` with the property list and `ObjectEditSlideOverTrigger`, the `ResourceSelector`, and the `<Outlet />`.
  - **Data**: `ResourcePoolDetailsBody` calls `useGetObject({ objectSchema: schema, objectId: poolId })` and `useGetPoolUtilization({ poolId })` itself. It renders the existing `LoadingIndicator` and `ErrorScreen` branches. It owns a `handleRefetchAll` that refetches the pool, refetches the utilization and invalidates `resourceManagerQueryKeys.all`, and passes it to `ObjectEditSlideOverTrigger`.
  - **What stays in `ResourcePoolContent`**: `Content.Card` and `Content.CardTitle` with the same title, reload and help button. Its reload refetches the pool and invalidates `resourceManagerQueryKeys.all`. It renders `<ResourcePoolDetailsBody …/>` below the title.
  - **Check**: an IP prefix pool page looks and behaves as before. `tests/e2e/resource-manager/test_resource_pool.py` must still pass in Phase 4.
- [X] T009 [P] Add `numberPool` to `src/entities/resource-manager/ui/queries/resource-manager.query-keys.ts::resourceManagerQueryKeys`:
  - Shape: `[...all, "number-pool", poolId, branchName, atDate]`.
  - Params interface: `NumberPoolKeysParams { poolId: string; branchName: string; atDate?: Date | null }`.

**Checkpoint**: the app behaves exactly as before, and every existing unit and component test passes (`cd frontend/app && pnpm test`).

---

## Phase 3: User Story 1 - Understand a number pool from its header (Priority: P1), the first deliverable

**Goal**: opening a number pool shows the new header:
- the name, the managed-by tag, the description and the ID
- the "Allocates to" sentence
- the metadata popover, the reload button and the Actions menu with the schema lock

IP pools are unchanged.

**Independent Test**: open the schema-created pool `InfraService.service_identifier [...]` and the user-created pool "number pool test for generic". Check every value in the header against the stored pool, and check which menu items are enabled (spec acceptance scenarios 1 to 6; quickstart.md "Manual check").

### Tests for User Story 1 (write first, confirm they fail)

- [X] T011 [P] [US1] Unit tests for `mapToNumberPoolData` in `src/entities/resource-manager/api/number-pool.mappers.test.ts` (data-model.md "NumberPoolData"). Cases:
  - `pool_type.value` `"Schema"` stays `"Schema"`; `"User"`, `null` or any other value gives `"User"`.
  - `allocation_scope.value` that is `null`, `[]`, `["site", "role"]`, or not a list of strings (for example `[1]` or `"site"`) gives `[]`, `[]`, `["site", "role"]` and `[]`.
  - A `description.value` that is empty or `null` gives `null`.
  - `id`, `hfid`, `display_label`, `node` and `node_attribute` are passed through, and `__typename` is `CoreNumberPool`.
- [X] T012 [P] [US1] Unit tests for `getNumberPool` in `src/entities/resource-manager/domain/use-cases/get-number-pool.test.ts`. Mock `getNumberPoolFromApi` with `vi.mock`. Cases:
  - One edge: returns the mapped `NumberPoolData`.
  - `errors` are present: throws, and the message joins them with `"; "`, as `getPoolUtilization` does.
  - No edge: throws `Number pool not found`.
- [X] T013 [P] [US1] Component tests for `NumberPoolHeader` and `NumberPoolHeaderSkeleton` in `src/entities/resource-manager/ui/number-pool/number-pool-header.test.tsx`:
  - **Setup**: build a `NumberPoolData` literal, set `nodeSchemasAtom` from `@/entities/schema/stores/schema.atom` with a schema for the pool's kind (restore it in `afterAll`), and pass `generatePermission()` from `frontend/app/tests/fake/permission.ts`. Mock the `NumberPoolActionsMenu` module, so these tests cover only the header.
  - **Schema-created pool**: heading level 1 with the name. A `button` "Managed by schema" that opens the `dialog` "Schema viewer" on the attribute (research.md R17).
  - **User-created pool**: no managed-by tag.
  - **Unscoped pool**: the text "Allocates to", a `button` for the kind, a `button` for the attribute, then "with no scope".
  - **Scope `["site", "role"]`**: "scoped by", then a `button` "Site" and a `button` "Role", from the schema labels.
  - **Schema modals**: selecting the kind, or a scope field, opens the `dialog` "Schema viewer".
  - **Scope field missing from the schema**: the stored field name shows, and no `button` has that name.
  - **Kind missing from the schema**: the kind name shows, and no `button` has that name.
  - **Description**: shown when set.
  - **ID**: the full ID shows, and a `button` "Copy ID" is present.
  - **Reload**: pressing `button` "Refresh data" invalidates `resourceManagerQueryKeys.all`.
  - **Header controls**: a `button` "View node metadata", a `button` "Refresh data" and a `button` "Actions" are present.
  - **`NumberPoolHeaderSkeleton`**: renders a `status` "Loading number pool" and no heading.
- [X] T014 [P] [US1] Component tests for `NumberPoolActionsMenu` in `src/entities/resource-manager/ui/number-pool/number-pool-actions-menu.test.tsx` (contract table "NumberPoolActionsMenu"). Open the menu by pressing `button` "Actions". Cases:
  - **Schema-created pool with full permission**: `menuitem` Edit, Groups and Delete are disabled. The tooltip on Edit and on Groups reads `Defined by the schema attribute <kind>.<attribute>`.
  - **View schema**: links to the `CoreNumberPool` schema.
  - **User-created pool with full permission**: Edit, Groups and Delete are enabled.
  - **User-created pool with `generatePermission({ update: false, delete: false })`**: Edit, Groups and Delete are disabled.
  - **Schema-created pool with no permission**: the tooltip on Delete shows the schema lock message, not the permission message.
  - **Keyboard**: typing "g" moves focus to `menuitem` "GraphQL sandbox".
  - **Documentation**: present only when `schema.documentation` is set, and its link uses `getDocumentationUrl`.
  - **Copy HFID**: absent when `hfid` is `null`, while Copy ID stays.

  Follow the pattern in `src/entities/repository/ui/repository-menu-section.test.tsx`.
- [X] T015 [P] [US1] Component tests for `NumberPoolDetailsPage` in `src/pages/resource-manager/number-pool-details.test.tsx`. Mock `useGetNumberPool` from `@/entities/resource-manager/ui/queries/get-number-pool.query`, and mock the `ResourcePoolDetailsBody` module to a stub. Cases:
  - **Pending**: the header skeleton shows, and no heading (FR-014).
  - **Error**: the error screen shows the error message.
  - **Loaded**: a heading with the pool name shows, and the body stub shows.

### Implementation for User Story 1

- [X] T016 [US1] Create `src/entities/resource-manager/api/get-number-pool-from-api.ts`, following `get-number-pools-from-api.ts::getNumberPoolsFromApi`:
  - Define `GET_NUMBER_POOL` with `graphql()` from `@/shared/api/graphql/client`: `query GET_NUMBER_POOL($ids: [ID]) { CoreNumberPool(ids: $ids) { edges { node { id hfid display_label __typename name { value } description { value } pool_type { value } node { value } node_attribute { value } allocation_scope { value } } } } }`.
  - Export `getNumberPoolFromApi({ poolId, branchName, atDate })`, with `GetNumberPoolFromApiParams extends ContextParams`, passing `ids: [poolId]` and the branch and date context exactly as `getNumberPoolsFromApi` does.
- [X] T017 [US1] Run `cd frontend/app && pnpm codegen:graphql` so gql.tada types `GET_NUMBER_POOL`. Keep the regenerated `src/shared/api/graphql/generated/graphql-cache.d.ts` and never edit it by hand.
- [X] T018 [US1] Create `src/entities/resource-manager/api/number-pool.mappers.ts` with `mapToNumberPoolData(node)`, which takes the generated node type of `GET_NUMBER_POOL` (use `ResultOf<typeof GET_NUMBER_POOL>` from the client module, or export a node type from T016) and returns `NumberPoolData`:
  - Compare `pool_type` against `NUMBER_POOL_TYPE_SCHEMA` (T001).
  - Narrow `allocation_scope.value` with a type guard that accepts only an array of strings.
  - T011 must pass.
- [X] T019 [US1] Create `src/entities/resource-manager/domain/use-cases/get-number-pool.ts`:
  - Export `GetNumberPoolParams = GetNumberPoolFromApiParams` and `getNumberPool(params): Promise<NumberPoolData>`.
  - Call the api, throw on `errors`, throw `new Error("Number pool not found")` when there is no edge, and otherwise return `mapToNumberPoolData(edge.node)`.
  - T012 must pass.
- [X] T020 [US1] Create `src/entities/resource-manager/ui/queries/get-number-pool.query.ts`, following `get-number-pools.query.ts`:
  - `getNumberPoolQueryOptions(params)` with the key `resourceManagerQueryKeys.numberPool(params)` (T009) and `queryFn: () => getNumberPool(params)`.
  - `useGetNumberPool(poolId: string)`, which reads `useCurrentBranch()` and `datetimeAtom` and passes `branchName` and `atDate`.
- [X] T022 [US1] Create `src/entities/resource-manager/ui/number-pool/number-pool-actions-menu.tsx` with `NumberPoolActionsMenu({ pool, schema, permission })` (research.md R3, R5, R8, R14):
  - **Trigger and layout**: copy the trigger, `Popover` and section layout of `ObjectDetailsMenu`, a `Button` "Actions" with `ChevronDownIcon`.
  - **Actions section**: `CopyToClipboardMenuItem` Copy ID. Copy HFID when `pool.hfid` is set.
  - **Go to section**, with the same icons as `ObjectDetailsMenu` (research.md R16):
    - Tasks: `getObjectTasksUrl(pool.id)`, icon `TasksStatusIcon`.
    - View schema: for every pool, `href` `/schema?kind=CoreNumberPool` built with `constructPath`, icon `mdi:code-json`.
    - GraphQL sandbox: `getObjectGraphqlSandboxUrl(NUMBER_POOL_KIND, pool.id)`, icon `mdi:graphql`.
    - Documentation: only when `schema.documentation` is set, `getDocumentationUrl`, `target="_blank"`, lucide icon `BookTextIcon`.
  - **Keyboard**: give every `MenuItem` an explicit `textValue`, so typing a letter moves focus to the item.
  - **Manage section**:
    - Edit, Groups and Delete: when `pool.pool_type.value === NUMBER_POOL_TYPE_SCHEMA`, use `{ isAllowed: false, message: \`Defined by the schema attribute ${pool.node.value}.${pool.node_attribute.value}\` }`. Otherwise Edit and Groups use `permission.update` and Delete uses `permission.delete`. Build this inline (R5).
  - **Overlays**, rendered after the menu as `ObjectDetailsMenu` does:
    - The "Manage groups" `Sheet` with `GroupsManager` (`schema`, `objectId: pool.id`).
    - The edit `Sheet` with `ObjectEdit` (`objectKind: NUMBER_POOL_KIND`, `objectId: pool.id`). Its `onUpdateComplete` invalidates `objectQueryKeys.all` and then `resourceManagerQueryKeys.all`, then closes the sheet (R14).
    - `ModalDeleteObject`, with `rowToDelete={pool}` and `onDelete` navigating to `getObjectDetailsUrl(NUMBER_POOL_KIND)` (R8).
  - Bind each `Sheet` to `isOpen` state. Don't render a sheet conditionally.
  - T014 must pass.
- [X] T023 [US1] Create `src/entities/resource-manager/ui/number-pool/number-pool-header.tsx`, exporting `NumberPoolHeader({ pool, schema, permission })` and `NumberPoolHeaderSkeleton()`. Lay it out as in the contract.
  - **First row, left**: an `h1` with the name (`truncate`, `title={pool.name.value}`), then `NodeMetadataPopover objectKind={NUMBER_POOL_KIND} objectId={pool.id}`, then the managed-by tag:
    - Schema-created: a button with `FileCodeIcon` and "Managed by schema" that opens `SchemaViewerModal` on the attribute (research.md R17). Its tooltip reads `Created from the ${pool.node.value}.${pool.node_attribute.value} schema attribute. Change its ranges in the schema.`
    - User-created: no tag (research.md R17).
  - **First row, right**: the full ID and `CopyToClipboardButton` with `aria-label="Copy ID"`. Then `RefreshButton queryKey={resourceManagerQueryKeys.all}` (research.md R2), and `NumberPoolActionsMenu`.
  - **Description**: a muted paragraph when `pool.description` is set.
  - **Sentence**: "Allocates to", then the kind, then "attribute", then the attribute name, then either "with no scope" or "scoped by" followed by one `ScopeFieldReference` per name in `pool.allocation_scope.value`, separated by "+".
    - Read `kindSchema` with `useSchema(pool.node.value)`.
    - The kind, the attribute and each scope field are `SchemaReference` elements that open `SchemaViewerModal` (research.md R15).
  - **Narrow screens**: the name shrinks and is cut first, the tag keeps its size (`shrink-0`), and the sentence wraps (`flex-wrap`).
  - **`NumberPoolHeaderSkeleton`**: a `status` "Loading number pool" with `Skeleton` placeholders for the name and for the Actions button, as `ObjectDetailsHeader` does while pending.
  - T013 must pass.
- [X] T024 [US1] Create `src/pages/resource-manager/number-pool-details.tsx`, exporting `NumberPoolDetailsPage({ poolId, schema, permission })`:
  - Call `useGetNumberPool(poolId)`.
  - **Pending**: render `NumberPoolHeaderSkeleton` and `ResourcePoolDetailsBody`.
  - **Error**: render `ErrorScreen` with `error.message`.
  - **Loaded**: render `Content.Card` containing `NumberPoolHeader`, then `ResourcePoolDetailsBody` (T008).
  - T015 must pass.
- [X] T025 [US1] In `src/pages/resource-manager/resource-pool-details.tsx::ResourcePoolContentWithPermissions`, render `NumberPoolDetailsPage` instead of `ResourcePoolContent` when `schema.kind === NUMBER_POOL_KIND`. Pass `resourcePoolId`, `schema` and `permission`. Every other kind keeps `ResourcePoolContent`.
- [X] T026 [US1] Extend `tests/e2e/resource-manager/test_number_pool.py::TestNumberPool`. Don't add a new spec file, keep the existing fixtures, and add each test after the test it depends on:
  - **`test_header_for_user_created_pool`**, after `test_displays_correct_details_for_created_number_pool`: go to `/resource-manager?branch={number_pool_branch}` and open "number pool test for generic". In the `header` that holds the level 1 heading, check:
    - `heading` with that name
    - no "Managed by" tag
    - "Allocates to", `button` "InfraInterface", and "with no scope"
    - in Actions, `menuitem` "Edit" and "Delete" are enabled
  - **`test_header_for_schema_created_pool`**, before `test_number_pool_attribute_kind_resource_manager`: open the `link` "InfraService." from the list. In the same `header`, check:
    - `button` "Managed by schema"
    - "Allocates to", `button` "InfraService", `button` "service_identifier", "with no scope"
    - selecting `button` "InfraService" opens the `dialog` "Schema viewer", and Escape closes it
    - in Actions, "Edit", "Groups" and "Delete" are disabled, and "View schema" links to the `CoreNumberPool` schema

  Use `expect(...)` assertions only, with no sleeps (`tests/e2e/README.md`).

**Checkpoint**: User Story 1 works on its own. The unit and component tests from T006 and T011 to T015 pass. A manual check following quickstart.md matches the acceptance scenarios.

---

## Phase 4: Polish and cross-cutting concerns

- [X] T027 Create the changelog fragment with `uv run towncrier create -c "Added a header to the number pool details page. It shows whether the schema manages the pool, what the pool allocates to and how the allocation is scoped. Its Actions menu disables Edit, Groups and Delete on pools that the schema created." +ifc-3364-number-pool-header.changed.md`. This writes `changelog/+ifc-3364-number-pool-header.changed.md` (research.md R13).
- [X] T028 [P] Run the frontend gate from `frontend/app/AGENTS.md` and fix every finding:
  - `cd frontend && pnpm exec biome ci .`
  - `cd frontend/app && pnpm knip`
  - `pnpm exec betterer ci`
  - `pnpm exec tsc --noEmit -p tsconfig.json`
  - `pnpm test`
- [X] T029 [P] Lint the end-to-end file: `uv run ruff check tests/e2e && uv run ruff format tests/e2e`.
- [X] T030 Run the end-to-end tests from quickstart.md:
  - `tests/e2e/resource-manager/test_number_pool.py`, with `--pdb` and `sleep infinity |` when it runs non-interactively
  - the regression files `tests/e2e/resource-manager/test_resource_pool.py` and `tests/e2e/test_breadcrumb.py`

  All must pass.
- [ ] T031 Follow the "Manual check" in quickstart.md on a running instance, including a pool with `allocation_scope` set through the GraphQL sandbox and a narrow window.
- [X] T032 If any implementation detail differs from `research.md`, `data-model.md` or `contracts/number-pool-header.md`, update every file in `dev/specs/ifc-3364-number-pool-header/` that states the old value, in the same commit (root `AGENTS.md`, "Always Do").

---

## Dependencies and execution order

### Phase dependencies

- **Phase 1** has no dependency.
- **Phase 2** depends on Phase 1 only for T009's types. T006 to T008 can start at once. Phase 2 blocks Phase 3.
- **Phase 3** depends on Phases 1 and 2.
- **Phase 4** depends on Phase 3.

### Order inside Phase 3

```text
T011, T012 ─▶ T016 ─▶ T017 ─▶ T018 ─▶ T019 ─▶ T020
T014 ─▶ T022
T013 ─▶ T023 (needs T022)
T015 ─▶ T024 (needs T020, T023) ─▶ T025 ─▶ T026
```

### Parallel opportunities

- **Phase 1**: T001 and T002 touch different files.
- **Phase 2**: T006 and T009 can start together. T008 is independent of T006 and T007.
- **Phase 3 tests**: T011 to T015 are all in separate files, so they can be written together.
- **Phase 3 implementation**: T022 and T023 can be written alongside T016 to T020.

### Parallel example: Phase 3 tests

```text
Task: "Unit tests for mapToNumberPoolData in src/entities/resource-manager/api/number-pool.mappers.test.ts"
Task: "Unit tests for getNumberPool in src/entities/resource-manager/domain/use-cases/get-number-pool.test.ts"
Task: "Component tests for NumberPoolHeader in src/entities/resource-manager/ui/number-pool/number-pool-header.test.tsx"
Task: "Component tests for NumberPoolActionsMenu in src/entities/resource-manager/ui/number-pool/number-pool-actions-menu.test.tsx"
Task: "Component tests for NumberPoolDetailsPage in src/pages/resource-manager/number-pool-details.test.tsx"
```

---

## Implementation strategy

- **First deliverable**: Phases 1 to 3. User Story 1 is the whole feature. Stop at the Phase 3 checkpoint and check it against the spec's acceptance scenarios.
- **Then**: Phase 4, which covers the changelog, the gates and the end-to-end run. These must pass before the pull request.
- **Commits**: one commit per phase works well. Phase 2 stands alone as a refactor that keeps behaviour, so a reviewer can read it apart from the new header.
