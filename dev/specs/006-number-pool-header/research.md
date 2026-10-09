# Research: Number pool details header

Each decision below resolves an open point in the plan's technical context. Code locations are given as `module::symbol`, relative to `frontend/app/src/` unless stated otherwise.

## R1. A number pool page that loads a typed number pool and passes it down

- **Decision**: the number pool page loads the pool through a new fetch path in the `resource-manager` entity. It passes the result, a `NumberPoolData` value, to `NumberPoolHeader`. Later work passes the same value to the new page body. The fetch path:

  ```text
  api/get-number-pool-from-api.ts       GET_NUMBER_POOL: CoreNumberPool(ids: [$id]), only the fields the page needs
  api/number-pool.mappers.ts            mapToNumberPoolData: API response → NumberPoolData
  domain/model/number-pool.ts           + NumberPoolData
  domain/use-cases/get-number-pool.ts   getNumberPool: calls the api and the mapper, throws when the pool is not found
  ui/queries/get-number-pool.query.ts   useGetNumberPool(poolId), key resourceManagerQueryKeys.numberPool
  ```

  - **Page**: `pages/resource-manager/number-pool-details.tsx::NumberPoolDetailsPage` calls `useGetNumberPool`. While the query loads, it renders `NumberPoolHeaderSkeleton` (FR-014). When the query fails, it renders the existing error screen.
  - **Query**: it is written with `graphql()` from `@/shared/api/graphql/client`, which types the response from the generated GraphQL schema, as `entities/resource-manager/api/get-number-pools-from-api.ts::getNumberPoolsFromApi` does.
  - **Branch and date**: they are passed as `ContextParams`, and the query key includes them, as `useGetNumberPools` does.
  - **Generated file**: gql.tada keeps a type cache of every `graphql()` document in `src/shared/api/graphql/generated/graphql-cache.d.ts`. After adding `GET_NUMBER_POOL`, run `pnpm codegen:graphql` and commit the regenerated cache. Never edit it by hand.
- **Rationale**:
  - **This is the first part of the new number pool page.** The future body needs the pool's ranges, which `useGetObject` does not fetch because it skips relationships that hold many nodes. A number pool fetch path is needed anyway, and this work starts it.
  - **One owner for the pool data.** The header now, and the body later, render from the same value, with no loading state in each part.
  - **Type safety (constitution III).** The response is typed from the generated schema, and the mapper narrows `pool_type` and `allocation_scope` once. No component reads `NodeObject` attributes or checks their types.
  - **Only the needed fields (constitution V).** The query asks only for what the page shows.
  - **The pattern the entity guideline names** for a new fetcher: api → use-case → `ui/queries`.
  - **Simpler header tests.** The header stays presentational, so its tests pass a `NumberPoolData` value instead of mocking a query hook.
- **Consequences**:
  - **Three requests for the pool for a while.** The number pool page loads the pool three times:
    - **Kind lookup** (existing): `ResourcePoolDetailsPage` calls `useGetObject` with the generic `CoreResourcePool` schema and no fields, only to learn the pool's kind (`__typename`).
    - **`GET_NUMBER_POOL`** (new): the fields the header needs.
    - **Body object** (existing): `ResourcePoolDetailsBody` calls `useGetObject` with the `CoreNumberPool` schema, every attribute with its metadata, and the single relationships, for the property list.

    Before this work, the page loaded the pool twice (the kind lookup and the body object). The body object goes away when the new body replaces `ResourcePoolDetailsBody`. The utilization and permission queries are unchanged and not counted here.
  - **The header needs an explicit reload after an edit.** The update mutation invalidates only the `"objects"` keys. See R14.
- **Alternatives considered**:
  - A pure rule that converts the `useGetObject` result into `NumberPoolData`. Rejected: the future body needs a dedicated query for the ranges anyway, and the generic result is loosely typed.
  - A header that fetches its own data, like `ObjectDetailsHeader`. Rejected: the future body would load the same pool again, and each part would handle loading on its own.

## R2. Reload that covers the pool, its utilization and its allocated resources

- **Decision**: the header renders the existing `entities/nodes/object/ui/object-details/refresh-button.tsx::RefreshButton` with `queryKey={resourceManagerQueryKeys.all}`. `RefreshButton` does not change.
- **Rationale**:
  - FR-007 asks for the same reload button as other detail pages, which is `RefreshButton`, with its "Last data refresh" tooltip.
  - FR-008 asks the reload to cover the pool, its utilization and its allocated resources. All three query keys start with `"resource-manager"`, and so do the queries of the new page body, so one prefix covers them.
  - The reload no longer refetches the unrelated queries mounted on the page, such as the branch list, the schema and permissions.
- **Cost**: the old body's properties card reads the pool through the `"objects"` query, which this reload does not cover. It shows stale values after a reload until the page body work replaces that card.
- **Alternatives considered**:
  - `queryKey={[]}`, which TanStack matches as a prefix of every key. It was the first decision, and covered the properties card too, but every reload refetched every query on the page. Replaced by the user on 2026-10-09.
  - Change `RefreshButton` to take a list of prefixes (`queryKeys`). Implemented first, then dropped by the user to keep the shared component out of this change.
  - Put the number pool key under `objectQueryKeys.all`. Rejected: the utilization and allocated-resource keys would still not reload, and the key would mix two entities' prefixes.
  - Use the page's `handleRefetchAll` with the generic `Retry` button. Rejected: it gives a different control from other detail pages, against FR-007.

## R3. Actions menu: reuse `ObjectDetailsMenu` or build a number pool menu

- **Decision**: build `NumberPoolActionsMenu` in `entities/resource-manager/ui/number-pool/`. It reuses the same building blocks as `entities/nodes/object/ui/object-details/object-details-menu.tsx::ObjectDetailsMenu`:
  - `CopyToClipboardMenuItem`
  - the "Manage groups" `Sheet` with `GroupsManager`
  - the edit `Sheet` with `ObjectEdit`
  - `entities/nodes/object/ui/modal-delete-object.tsx::ModalDeleteObject`
- **Rationale**:
  - `ObjectDetailsMenu` can disable Edit and Delete only from `permission`. FR-010 needs a second reason, the schema lock, with its own tooltip.
  - `ObjectDetailsMenu` shows "Find paths" and "Convert object type", which the prototype leaves out. Converting a pool to another kind has no meaning.
  - Adding props for disabling, extra items and hidden items to `ObjectDetailsMenu` would add options that only one caller uses.
- **Alternatives considered**: extend `ObjectDetailsMenu` with `editDecision`, `deleteDecision`, `extraGoToItems` and `hiddenItems` props. Rejected for the reasons above.

## R4. Duplicated URL builders for Tasks, GraphQL sandbox and Documentation

- **Decision**: move the three inline URL builders into `entities/nodes/object/ui/routing/object-urls.ts` as `getObjectTasksUrl`, `getObjectGraphqlSandboxUrl` and `getDocumentationUrl`. Use them from `ObjectDetailsMenu`, `entities/artifacts/ui/artifact-details-menu.tsx::ArtifactDetailsMenu` and the new menu.
- **Rationale**: the same three builders are already written inline in two menus, and the new menu would add a third copy. Constitution principle VII allows extraction once two callers exist. The entity guideline puts URL builders in `ui/routing/`.
- **Alternatives considered**: inline a third copy. Rejected: three copies of a URL format drift apart.

## R5. Edit, Groups and Delete state when a pool is schema-created and the user lacks permission

- **Decision**: the menu builds the decision for each item inline:
  - **Edit, Groups and Delete**: when `pool_type` is `"Schema"`, disabled with the message `Defined by the schema attribute <kind>.<attribute>`. Otherwise, Edit and Groups use `permission.update` and Delete uses `permission.delete`.
  - **Why Groups is locked too**: changing a pool's groups is an update of the pool, and a schema-managed pool must not be changed from the page at all (decided by the user on 2026-10-09; Groups were allowed in the first version of this decision).
- **Rationale**: the schema lock applies to every user, so its message is the more useful one when both reasons apply. The derivation is two lines with one caller, so it stays inline and is not a domain rule.
- **Alternatives considered**: a `combinePermission` helper in `entities/permission/domain/rules/`. Rejected: it would have one caller.

## R6. Pool type vocabulary

- **Decision**: add `NUMBER_POOL_TYPE_SCHEMA = "Schema"` to `entities/resource-manager/domain/model/pool.ts`, next to `NUMBER_POOL_KIND`. Add `NUMBER_POOL_TYPE_USER = "User"` and the `NumberPoolType` union next to it. The mapper narrows `pool_type` to that union, and the header and menu compare `pool.pool_type.value` against `NUMBER_POOL_TYPE_SCHEMA`.
- **Rationale**: the value is part of the `pool_type` enum that the backend defines (`backend/infrahub/core/constants/__init__.py::NumberPoolType`). Comparing against it is vocabulary, like the kind constants in the same file, not a mirrored default.
- **Alternatives considered**: read the enum from the attribute schema at runtime. Rejected: it gives no extra safety, because the comparison still needs the literal.

## R7. Labels of the allocation scope fields, and the schema modal tab

- **Decision**:
  - `ScopeFieldReference` looks up each scope field inline: one `find` by name over the kind schema's attributes and relationships. The label is the field's `label`, or its name when the label is empty or the field is missing. A field missing from the schema, or a kind missing from the current branch, shows the stored name and opens nothing.
  - `SchemaReference` picks the modal tab itself from its `schema` and `targetField`: the relationships tab when a relationship has that name, the attributes tab otherwise, and the default Properties tab when there is no target field (the kind). Callers pass only `targetField`.
- **Rationale**:
  - The tab is fully determined by the field, so callers should not compute it. Keeping the computation in `SchemaReference` leaves the shared `SchemaViewer` unchanged.
  - The lookup is one `find` with one caller, so it stays in the component rather than becoming a domain rule. The header component tests cover the fallback cases.
- **Alternatives considered**:
  - A pure rule `getAllocationScopeFields` returning `{ name, label, fieldType }`. Implemented first, then removed.
  - Checking `isRelationshipSchema` on the found field in `ScopeFieldReference` and passing `defaultTab`. Replaced by the computation in `SchemaReference`.
  - Letting `SchemaViewer` derive the tab from `targetField` for every caller. Not chosen, to keep the shared component unchanged.

## R8. Delete destination

- **Decision**: render `ModalDeleteObject` with `onDelete` navigating to `getObjectDetailsUrl(NUMBER_POOL_KIND)` (`entities/nodes/object/ui/routing/object-urls.ts::getObjectDetailsUrl`).
- **Rationale**: for any kind that inherits from `CoreResourcePool`, that function returns `/resource-manager/`, the resource manager list (FR-013). This is the same call `ObjectDetailsMenu` makes for a node without a parent.

## R9. Pool ID

- **Decision**: the header renders the full ID, without a tooltip, and `shared/components/buttons/copy-to-clipboard-button.tsx::CopyToClipboardButton` for the full ID, as the prototype does.
- **Rationale**: `shared/components/ui/id.tsx::Id` shows the node label, not the ID, and fetches the label again. No other shared component shows an ID with a copy button. The prototype showed the first 8 characters with the full ID in a tooltip; the user chose the full ID after testing.

## R10. How the route reaches the number pool page

- **Decision**:
  - In `pages/resource-manager/resource-pool-details.tsx::ResourcePoolContentWithPermissions`, render `NumberPoolDetailsPage` when the resolved kind is `NUMBER_POOL_KIND`. Every other pool kind keeps `ResourcePoolContent`.
  - Move the current page body out of `ResourcePoolContent` into `pages/resource-manager/resource-pool-details-body.tsx::ResourcePoolDetailsBody`. That body is the side card with the property list, the utilization, the resource list and the `Outlet`. Both pages render it, and its behaviour does not change.
  - `ResourcePoolDetailsBody` takes `poolId`, `schema` and `permission`, and keeps today's `useGetObject` and utilization fetches. For IP pools it shares the cached request with the page title, so they send no extra request.
- **Rationale**:
  - FR-001 and SC-004 require the other pool kinds to be unchanged.
  - The route `/resource-manager/:resourcePoolId` serves every pool kind, and the page learns the kind only after the first fetch, so the switch happens after that fetch and not in the router.
  - Sharing the body keeps "page body unchanged" true for number pools without copying it. The future number pool body replaces `ResourcePoolDetailsBody` inside `NumberPoolDetailsPage` only.
- **Alternatives considered**:
  - A separate route for number pools. Rejected: links to `/resource-manager/<id>` already exist for every pool kind (`getObjectDetailsUrl`), and the route cannot know the kind before fetching.
  - Copy the body into the number pool page. Rejected: two copies of the same body until the body work.

## R11. Testing

- **Decision**:
  - **Unit tests**:
    - `number-pool.mappers.test.ts`: `pool_type`, an empty or null `allocation_scope`, a missing description
    - `get-number-pool.test.ts`: the pool is returned, the API returns errors, the pool is not found
  - **Component tests** (Vitest browser mode, next to the source, `tests/components/render.tsx`):
    - `number-pool-header.test.tsx` and `number-pool-actions-menu.test.tsx`. They pass a `NumberPoolData` value, set `nodeSchemasAtom`, and use `tests/fake/permission.ts::generatePermission`. No query hook is mocked for the header.
    - `pages/resource-manager/number-pool-details.test.tsx`: mocks `useGetNumberPool` and checks the three page states. While loading, `NumberPoolHeaderSkeleton` shows (FR-014). On error or when the pool is not found, the error screen shows. When loaded, the header shows.
  - **End-to-end test**: extend `tests/e2e/resource-manager/test_number_pool.py::TestNumberPool` (repository root):
    - the schema-created pool `InfraService.service_identifier`, which `models/base/service.yml` creates in every data slice
    - the user-created pool "number pool test for generic" that the class already creates
- **Rationale**:
  - Constitution principle IV requires an end-to-end test for user-facing features. Extending the existing spec reuses its branch fixture and pools.
  - No end-to-end data sets `allocation_scope`, so the "scoped by" sentence and the missing-field fallback are covered by component tests.
- **Effect on existing tests**: `tests/e2e/resource-manager/test_resource_pool.py` and `tests/e2e/test_breadcrumb.py` test IP prefix pools, so this change does not affect them. `test_number_pool.py::test_number_pool_attribute_kind_resource_manager` saves a documentation screenshot of the schema-created pool. The screenshot will change, and docs screenshots are updated at the end of the epic.

## R12. Known limitation that is not addressed: the edit form on multi-range pools

- **Finding**: `entities/resource-manager/ui/number-pool-form.tsx::NumberPoolForm`, which Actions → Edit opens, requires `start_range` and `end_range`. On a pool with more than one range, both are null, so the user cannot save a new name or description.
- **Decision**: out of scope. The spec keeps the existing edit form. The range editor in the page body work replaces it. The tests for FR-012 use a pool with a single range.

## R13. Changelog

- **Decision**: `changelog/+ifc-3364-number-pool-header.changed.md`, created with `uv run towncrier create`.
- **Rationale**: the project's changelog skill says to use a `+` slug when there is no GitHub issue, and never a bare Jira ID. `changed` fits because the existing details page changes.

## R14. Reloading the header after an edit

- **Decision**: `NumberPoolActionsMenu` passes an `onUpdateComplete` to the edit sheet that invalidates `resourceManagerQueryKeys.all`, after the update mutation has invalidated the `"objects"` keys.
- **Rationale**: `entities/nodes/object/ui/queries/update-object.mutation.ts::useUpdateObjectMutation` invalidates only `objectQueryKeys.all` and the edit-form keys. The number pool query key starts with `"resource-manager"`, so without this the header keeps showing the old name or description (FR-012). The utilization query has the same prefix and also reloads, which matches what `handleRefetchAll` does on the page today.
- **Alternatives considered**: make the generic update mutation invalidate resource-manager keys. Rejected: it would make the shared node mutation depend on one entity.

## R15. Schema references open the schema in a modal

- **Decision**: in the sentence, the kind, the attribute and each scope field use the style the kind had as a link: medium weight with a dotted underline that turns solid on hover. Selecting one opens `entities/schema/ui/schema-viewer-modal.tsx::SchemaViewerModal` inside a react-aria `DialogTrigger`. For a field, the modal opens on the matching tab with `targetField`.
- **Rationale**: the user reported, after testing, that the three references looked different and that leaving the page to read the schema was disruptive. `SchemaViewerModal` already serves the field labels on object detail rows (`entities/nodes/object/ui/object-details/object-data-display/object-data-row.tsx::ObjectDataRow`) with the same trigger pattern.
- **Same pattern on the tag**: the "Managed by schema" tag opens the same modal on the attribute that created the pool (R17).

## R16. "View schema" instead of "Schema attribute" in the Actions menu

- **Decision**: the Go to section shows "View schema" for every pool, linking to the `CoreNumberPool` schema page. The "Schema attribute" item from the prototype is removed.
- **Rationale**: "Schema attribute" went to the schema page of the pool's kind, because the schema page cannot open a single attribute, so the label promised more than it delivered. "View schema" matches the object details menu, and its label matches its destination. The defining attribute stays reachable from the header sentence (schema modal on the attribute) and the "Managed by schema" tag.
- **Icon**: the iconify `mdi:code-json` the object details menu uses, so both menus show the same icons. Tasks and GraphQL sandbox also reuse that menu's icons (`TasksStatusIcon`, `mdi:graphql`), as the user asked on 2026-10-09.

## R17. The managed-by tag shows only for schema-created pools and opens the attribute

- **Decision**: the header shows the "Managed by schema" tag only when `pool_type` is `"Schema"`. User-created pools show no tag. Selecting the tag opens `SchemaViewerModal` for the pool's kind, on the attributes tab, focused on `node_attribute`. The tooltip naming the attribute stays.
- **Rationale**: the user decided after testing that only the exception needs a label, since most pools are created by users. Opening the attribute in a modal matches the schema references in the sentence (R15) and lands on the exact field that created the pool, which the schema page cannot do.
- **Alternatives considered**: keep a "Managed by users" tag. Rejected by the user.

