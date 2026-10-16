# Tasks: IP Prefix Tree Map

**Input**: Design documents from `dev/specs/ifc-3300-ip-prefix-treemap/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/graphql-query.md, contracts/ui-contract.md, quickstart.md

**Rework note (2026-10-04)**: the task descriptions below record the first implementation as it was
executed. After review, T003, T004, T012, T013 and T015 were superseded: CIDR parsing became
`prefix-size.ts` fed by the API's `prefixlen` and `version`, the squarified layout became an
address-ordered Hilbert-curve layout, aggregation moved to one tile per full cell (a cell cut by
the cap uses aligned CIDR blocks of its loaded portion), the remainder tile
became the not-loaded range, and the use-case now fetches the parent itself. See
opsmill-implement-report.md, Erratum 6; the design documents already reflect the current state.

**Tests**: Included. The constitution's Test Discipline principle requires unit, component and E2E coverage written alongside implementation, and the spec's success criteria are verified by them.

**Organization**: Tasks are grouped by user story so each story is an independently testable increment. Paths are relative to the repository root. Frontend source is under `frontend/app/src/`, abbreviated below as `FE/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1 to US5)
- Every task names the file it touches; sites inside a file are named by symbol, never by line

## Path Conventions

- `FE/entities/ipam/ip-prefixes/` holds the api, domain and ui layers for this feature
- `FE/pages/ipam/` holds the route shim and the tab bar
- `tests/e2e/ipam/` holds the Playwright journeys
- Before touching a frontend file, load `dev/guidelines/frontend/component-patterns.md`, `route-architecture.md`, `typescript.md` and `styling.md`, and `dev/knowledge/frontend/react.md` before any effect code

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: The domain model and the query-key factory every later task imports

- [X] T001 Create the domain model and constants in `FE/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map.ts`: export the types `PrefixSize`, `TreeMapChild`, `TreeMapFreeBlock`, `TreeMapData`, `TreeMapTile` (discriminated union on `kind`: `allocated`, `free`, `aggregate-allocated`, `aggregate-free`, `remainder`) and `TreeMapRect` exactly as data-model.md defines them, plus the constants `TREE_MAP_CHILD_LIMIT = 1000`, `TREE_MAP_MIN_TILE_DIVISOR = 4096n` and `TREE_MAP_ASPECT_RATIO = 2`. No functions in this file.
- [X] T002 [P] Create the query-key factory in `FE/entities/ipam/ip-prefixes/ui/queries/ip-prefix.query-keys.ts` exporting `ipPrefixesQueryKeys` with one entry, `treeMap: (params: IpPrefixTreeMapKeysParams) => [...objectQueryKeys.allWithContext(params), "ip-prefix-tree-map", params] as const`, where the params interface extends `ContextParams` with `parentId: string` and `limit: number`. Rooting under `objectQueryKeys` is what lets existing mutations invalidate the map.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: CIDR parsing, the typed query, the use-case and the hook. Every story reads data through these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 [P] Write the unit tests for CIDR parsing in `FE/entities/ipam/ip-prefixes/domain/rules/parse-prefix-length.test.ts`: `10.0.0.0/8` gives `ipv4`, length 8, `16777216n` addresses; `2001:db8::/32` gives `ipv6`, length 32, `2n ** 96n`; `::/0` and `0.0.0.0/0` give the full space; `10.0.0.0/33`, `2001:db8::/129`, a string without `/`, and an empty string each throw. One GIVEN, WHEN, THEN per test.
- [X] T004 [P] Implement `parsePrefixLength(cidr: string): PrefixSize` in `FE/entities/ipam/ip-prefixes/domain/rules/parse-prefix-length.ts`: detect the family from `:`, parse the integer after `/`, validate the range, compute `addressCount = 1n << BigInt(maxLength - prefixLength)`. Throw a plain `Error` with a message naming the input for invalid strings. No IP-address normalisation beyond that; the backend owns CIDR validity.
- [X] T005 Create the typed query in `FE/entities/ipam/ip-prefixes/api/get-ip-prefix-tree-map-from-api.ts`: export `GET_IP_PREFIX_TREE_MAP` built with `graphql` from `@/shared/api/graphql/client`, copying the document from contracts/graphql-query.md verbatim, and export `getIpPrefixTreeMapFromApi({ parentId, limit, branchName, atDate })` that calls `graphqlClient.query` with `variables: { parentIds: [parentId], limit }` and `context: { branch: branchName, date: atDate }`, mirroring `FE/entities/ipam/ipam-tree/api/get-ipam-tree-nodes-by-parent-from-api.ts::GetIpamTreeNodesByParentFromApi`.
- [X] T006 [P] Write the use-case tests in `FE/entities/ipam/ip-prefixes/domain/use-cases/get-ip-prefix-tree-map.test.ts` using `vi.mock` on the api module and the sandbox sample from contracts/graphql-query.md as the mocked response: three `TreeMapChild` entries in address order with `memberCount` taken from `ip_addresses.count` for the address-type child and `children.count` for the others; free blocks parsed from `prefix.value`; `totalChildCount` equals `count`; `isCapped` is false; a node with a null `prefix.value` is dropped; a response where `count` exceeds the real children sets `isCapped` true.
- [X] T007 Implement `getIpPrefixTreeMap(params: GetIpPrefixTreeMapParams): Promise<GetIpPrefixTreeMapResult>` in `FE/entities/ipam/ip-prefixes/domain/use-cases/get-ip-prefix-tree-map.ts`: params carry `parentId`, `limit`, `branchName`, `atDate`; split edges on `node.__typename === IP_PREFIX_AVAILABLE_KIND` (import from `domain/model/ip-prefix.ts`); map real nodes to `TreeMapChild` and available nodes to `TreeMapFreeBlock`; parse CIDRs with `parsePrefixLength` and skip nodes that throw; return `children`, `freeBlocks`, `totalChildCount` and `isCapped`. The parent is not part of the result; the caller already holds it.
- [X] T008 Create the hook in `FE/entities/ipam/ip-prefixes/ui/queries/get-ip-prefix-tree-map.query.ts`: export `getIpPrefixTreeMapQueryOptions(params)` returning `queryOptions({ queryKey: ipPrefixesQueryKeys.treeMap(params), queryFn: () => getIpPrefixTreeMap(params) })` and `useGetIpPrefixTreeMap({ parentId })` that fills `branchName` from `useCurrentBranch().currentBranch.name`, `atDate` from `useAtomValue(datetimeAtom)` and `limit` from `TREE_MAP_CHILD_LIMIT`, following `FE/entities/permission/ui/queries/get-object-permissions.query.ts::useGetObjectPermissions`.

**Checkpoint**: `pnpm test -- src/entities/ipam/ip-prefixes/domain` passes; the hook compiles.

---

## Phase 3: User Story 1 - See where a prefix's space has gone (Priority: P1) 🎯 MVP

**Goal**: The Tree Map tab exists on prefix pages and renders direct children and free blocks as proportionally sized tiles with utilisation fills and hover details.

**Independent Test**: Open the Tree Map tab on 10.0.0.0/8 in the demo data and compare the tiles, their relative areas, fills and tooltips against the Children tab.

### Tests for User Story 1

- [X] T009 [P] [US1] Write `FE/entities/ipam/ip-prefixes/domain/rules/build-tree-map-tiles.test.ts` covering the non-aggregated cases: three /16 children and the demo's free blocks inside a /8 produce one tile per input with `addressCount` summing exactly to `2n ** 24n` and `weight` summing to 1 within 1e-6; a fully allocated parent produces no `free` tile; an empty parent with two half-size free blocks produces two `free` tiles; a child with `utilization: null` keeps `null` on its tile; tiles come out sorted by `weight` descending with ties in address order.
- [X] T010 [P] [US1] Write `FE/entities/ipam/ip-prefixes/domain/rules/layout-tree-map.test.ts`: for weights `[0.5, 0.25, 0.25]` and `[1]` and a random set of twenty weights normalised to 1, every rect lies within `0..100` on both axes, no two rects overlap, and `width * height / 10000` equals the tile's weight within 1e-6, at aspect ratios 1 and 2.
- [X] T011 [P] [US1] Write `FE/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map-tile.test.tsx` with `render` from `frontend/app/tests/components/render.tsx`: an `allocated` tile at 0, 50 and 100 percent exposes a link named `"<CIDR>, <N>% utilised"` and an inner fill whose inline width matches; an allocated tile with `utilization: null` is named `"<CIDR>, utilisation unknown"` and has no fill; a `free` tile exposes a button named `"<CIDR> available"`; every tile carries `data-testid="ip-prefix-tree-map-tile"` and the matching `data-tile-kind`.

### Implementation for User Story 1

- [X] T012 [US1] Implement `buildTreeMapTiles({ parent, children, freeBlocks, totalChildCount }): TreeMapTile[]` in `FE/entities/ipam/ip-prefixes/domain/rules/build-tree-map-tiles.ts`: compute the threshold `parent.size.addressCount / TREE_MAP_MIN_TILE_DIVISOR` in BigInt; emit `allocated` and `free` tiles at or above it; collect those below it into one `aggregate-allocated` and one `aggregate-free` tile (omitted when empty); when `totalChildCount` exceeds `children.length`, emit one `remainder` tile whose `addressCount` is the parent's count minus the sum of all children and free blocks, omitted when zero; derive `weight` as `Number(addressCount * 1_000_000n / parent.size.addressCount) / 1_000_000`; sort by `weight` descending then by address order; set `label` per data-model.md. Keep it one exported function plus small private helpers, each under fifty lines.
- [X] T013 [P] [US1] Implement `layoutTreeMap(tiles: TreeMapTile[], aspectRatio: number): TreeMapRect[]` in `FE/entities/ipam/ip-prefixes/domain/rules/layout-tree-map.ts` as the squarified algorithm: lay out in a `aspectRatio x 1` box, fill rows along the shorter side, add a tile to the current row while the row's worst aspect ratio does not get worse, then fix the row and recurse on the remaining box; scale the result to percentages. Pure, no DOM, no React.
- [X] T014 [US1] Create `FE/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map-tile.tsx` exporting `IpPrefixTreeMapTile({ rect, parent, permission, onCreateFromFreeBlock })`: position with inline `left/top/width/height` percentages inside an absolutely positioned wrapper; `allocated` renders a react-router `Link` to `getObjectDetailsUrl(child.kind, child.id, undefined, "tree-map")` with `bg-accent-surface border border-border` and an inner `div` of `width: <utilization>%` using `background: color-mix(in oklch, var(--accent-strong) 55%, transparent)`; `free` renders an `@infrahub/ui` `Button` with `bg-subtle border-dashed border-border-strong text-foreground-muted`, `isDisabledAndFocusable` when `!permission.create.isAllowed`, wrapped in `Tooltip` with `permission.create.message` when disabled; `aggregate-allocated` and `remainder` render a `Link` to `getObjectDetailsUrl(parent.kind, parent.id, undefined, "children")`; `aggregate-free` renders a `div`. Every tile gets `data-testid`, `data-tile-kind` and the accessible names from contracts/ui-contract.md. Make each tile an `@container` and show the label only from `@min-[5rem]`. Wrap every tile in the `@infrahub/ui` `Tooltip` whose `message` lists CIDR, description, member type, utilisation and member count for allocated tiles and the CIDR for free tiles. No `dark:` classes, no fixed palette colours.
- [X] T015 [US1] Create `FE/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map.tsx` exporting `IpPrefixTreeMap({ parent, parentSchema, permission })`: call `useGetIpPrefixTreeMap({ parentId: parent.id })`; render `LoadingIndicator` while pending and `ErrorScreen` on error; build tiles with `buildTreeMapTiles` and rects with `layoutTreeMap(tiles, TREE_MAP_ASPECT_RATIO)`; render a `div` with `role="group"`, `aria-label="Tree map of <parent.cidr>"`, `data-testid="ip-prefix-tree-map"`, `relative w-full aspect-[2/1]` containing one `IpPrefixTreeMapTile` per rect; render a legend row below with "Allocated", "Free" and "Smaller than 1/4096 of the prefix" swatches using the same token classes as the tiles. Leave the create handler as a no-op placeholder that US3 replaces, and leave the cap notice to US5.
- [X] T016 [US1] Create the route shim `FE/pages/ipam/ipam-details-tree-map-page.tsx` exporting `Component`: read `parentSchema` and `parentData` from `useCurrentFormContext()` as `FE/pages/ipam/ipam-details-index-page.tsx::IpamDetailsIndexPage` does, return `ErrorScreen` when either is missing; derive `parent = { id, kind: parentSchema.kind, cidr: prefix.value, size: parsePrefixLength(cidr), memberType: member_type.value, utilization: utilization.value ?? null }` by reading the attributes through `NodeAttribute` without `as` casts (narrow with `typeof` checks); wrap in `RequireObjectPermissions objectKind={parentSchema.kind}` and render `IpPrefixTreeMap` with the permission it yields. Keep the shim under thirty lines; move any helper into `domain/rules/`.
- [X] T017 [US1] Register the route in `FE/app/router.tsx`: inside the `ipam/:objectKind/:objectId` children array add `{ path: "tree-map", lazy: () => import("@/pages/ipam/ipam-details-tree-map-page") }` before the `:relationshipName` entry.
- [X] T018 [US1] Add the tab in `FE/pages/ipam/ipam-details-layout.tsx::IpamDetailsTabs`: after the Details `LinkTab`, when `isOfKind(IP_PREFIX_GENERIC, objectSchema)` render `<LinkTab to={constructPathForIpam("tree-map")}>` with a lucide `LayoutDashboardIcon` (`className="size-4"`) and the label "Tree Map". Do not reorder the relationship tabs.
- [X] T019 [US1] (E2E executed in CI, passing) Write the E2E module `tests/e2e/ipam/test_ip_prefix_tree_map.py` with `pytestmark = pytest.mark.shard_foundation` and a class `TestIpPrefixTreeMapView` using the anonymous `page` and `data_ipam_pools`: navigate to `/ipam`, click the `10.0.0.0/8` link in `identifier-cell`, click `get_by_role("link", name="Tree Map")`, assert `get_by_test_id("ip-prefix-tree-map")` is visible, assert links whose names start with the CIDRs `10.0.0.0/16`, `10.1.0.0/16` and `10.2.0.0/16` followed by a comma, and a button named `10.3.0.0/16 available`; a second test asserts the legend text. Add a third test for scenario 6 using a function-scoped branch fixture (copy the pattern from `tests/e2e/ipam/test_ip_prefix_create.py`) that creates `10.5.0.0/16` under `10.0.0.0/8` with the SDK client on the branch, asserts its tile appears on `/ipam/...?branch=<name>` and is absent on the default branch. Follow `tests/e2e/README.md` on fixtures and escape `/` in regex locators. Run `uv run ruff check tests/e2e && uv run ruff format tests/e2e`.

**Checkpoint**: `pnpm test -- src/entities/ipam/ip-prefixes` passes; the E2E view class passes with `uv run pytest -c tests/e2e/pytest.ini tests/e2e/ipam/test_ip_prefix_tree_map.py -s --pdb`; the tab is visible on 10.0.0.0/8 and absent on an IP address detail page.

---

## Phase 4: User Story 2 - Drill down into a child (Priority: P2)

**Goal**: Clicking an allocated tile lands on that child's Tree Map tab with branch and namespace preserved.

**Independent Test**: From 10.0.0.0/8's map, click the 10.1.0.0/16 tile and check the heading, the active tab and the query string.

### Tests for User Story 2

- [X] T020 [P] [US2] Extend `FE/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map-tile.test.tsx`: with `window.history.replaceState` setting `?namespace=abc` before render, an allocated tile's link `href` ends with `/ipam/<kind>/<id>/tree-map?namespace=abc`; an `aggregate-allocated` tile's `href` ends with `/children?namespace=abc`. Reset history after each test.

### Implementation for User Story 2

- [X] T021 [US2] Verify in `FE/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map-tile.tsx` that the allocated tile uses `getObjectDetailsUrl` with the `tree-map` tab segment and that `IP_PREFIX_GENERIC` kinds resolve to the `/ipam/` family (see `FE/entities/nodes/object/ui/routing/object-urls.ts::getObjectDetailsUrl`); adjust only if T020 fails. No other code change is expected.
- [X] T022 [US2] (E2E executed in CI, passing) Add `TestIpPrefixTreeMapDrillDown` to `tests/e2e/ipam/test_ip_prefix_tree_map.py`: open 10.0.0.0/8's Tree Map, click the `10.1.0.0/16` tile link, assert `get_by_role("heading", name="10.1.0.0/16")`, assert the `Tree Map` link has `aria-current="page"` (or the active class `LinkTab` applies; check `FE/shared/components/ui/link.tsx::LinkTab` for the attribute it sets), and assert the URL still contains the `namespace` param it had before the click. Scenario 2 (drilling into the address-type 10.0.0.0/16) is added in US4's E2E task because it depends on the empty state.

**Checkpoint**: US1 and US2 E2E classes pass.

---

## Phase 5: User Story 3 - Allocate into a hole from the map (Priority: P2)

**Goal**: A free tile opens the existing Create IP Prefix form prefilled with its CIDR; on success the map refreshes.

**Independent Test**: On a throwaway branch, click a free tile, save the prefilled form, see the new allocated tile without a reload; as a read-only user, see the free tile disabled with the permission message.

### Tests for User Story 3

- [X] T023 [P] [US3] Extend `FE/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map-tile.test.tsx`: with `permission.create.isAllowed` false and a message, the free button is disabled and the tooltip shows the message on hover; with it allowed, clicking the button calls `onCreateFromFreeBlock` with the block. Use `PERMISSION_ALLOW_ALL` and `PERMISSION_DENY_ALL` from `FE/entities/permission/domain/model/permission.ts`.

### Implementation for User Story 3

- [X] T024 [US3] Extract the create sheet from `FE/entities/ipam/ip-prefixes/ui/ip-prefix-available-identifier.tsx::IpPrefixAvailableIdentifier` into `FE/entities/ipam/ip-prefixes/ui/ip-prefix-create-sheet.tsx` exporting `IpPrefixCreateSheet({ schema, prefix, isOpen, onOpenChange, onSuccess })`: move the `Sheet`, `SlideOverTitle` and `ObjectForm` block as is, build the `currentObject.prefix` attribute from `prefix`, and derive `kind` from `schema.kind` with a proper guard instead of the existing `!` assertion. Update `IpPrefixAvailableIdentifier` to render `IpPrefixCreateSheet` with its existing `selectedSchema`, keeping the `objectQueryKeys.all` invalidation in its `onSuccess`. Behaviour of the Children tab must not change.
- [X] T025 [US3] Wire the sheet into `FE/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map.tsx::IpPrefixTreeMap`: hold `selectedFreeBlock: TreeMapFreeBlock | null` in state, pass `onCreateFromFreeBlock={setSelectedFreeBlock}` to the tiles, render `IpPrefixCreateSheet` with `schema={parentSchema}`, `prefix={selectedFreeBlock?.cidr}`, `isOpen={selectedFreeBlock !== null}`, and in `onSuccess` clear the state and call `queryClient.invalidateQueries({ queryKey: objectQueryKeys.all })` (import `queryClient` from `@/shared/api/rest/client` as the identifier does). No effect hooks.
- [X] T026 [US3] (E2E executed in CI, passing) Add `TestIpPrefixTreeMapCreate` to `tests/e2e/ipam/test_ip_prefix_tree_map.py` with a throwaway-branch fixture and `admin_page`, following `tests/e2e/ipam/test_ip_prefix_create.py::TestAllocateIpPrefix`: open the Tree Map of the same parent that test allocates into (confirm the prefix exists in `tests/e2e/data/ipam_pools.py`), click the free tile button, assert `get_by_label("Prefix *")` holds the CIDR, click Save, assert the success toast, then assert a link whose name starts with that CIDR is visible without calling `goto` again. Add a second test with `read_only_page` asserting the free button is disabled.

**Checkpoint**: Children tab still passes `tests/e2e/ipam/test_ip_prefix_create.py`; US3 E2E class passes.

---

## Phase 6: User Story 4 - Open the tab on an address-member prefix (Priority: P3)

**Goal**: Address-type prefixes show a meter, an explanation and a link to IP Addresses instead of a map.

**Independent Test**: Open the Tree Map tab on 10.0.0.0/16 and check the empty state.

### Tests for User Story 4

- [X] T027 [P] [US4] Write `FE/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map-empty-state.test.tsx`: rendering with utilisation 12 shows a meter named `Utilization` with value 12, the explanation text, and a link named `IP Addresses` whose `href` ends with `/ip_addresses`; rendering with utilisation `null` shows the text and link and no meter.

### Implementation for User Story 4

- [X] T028 [P] [US4] Create `FE/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map-empty-state.tsx` exporting `IpPrefixTreeMapEmptyState({ utilization })`: `data-testid="ip-prefix-tree-map-empty"`, the `@infrahub/ui` `Meter` with `aria-label="Utilization"` inside a `w-40` wrapper (same as `FE/entities/ipam/ip-prefixes/ui/get-ip-prefix-table-columns.tsx` renders it) when `utilization` is a number, the text "This prefix holds IP addresses. The tree map shows child prefixes.", and a react-router `Link` to `constructPathForIpam("ip_addresses")` labelled "IP Addresses". Reuse the layout of `FE/shared/components/errors/no-data-found.tsx` for spacing and muted text.
- [X] T029 [US4] In `FE/pages/ipam/ipam-details-tree-map-page.tsx::Component`, when `parent.memberType === "address"` render `IpPrefixTreeMapEmptyState` instead of `IpPrefixTreeMap`, before any query runs. Keep the `RequireObjectPermissions` wrapper around the map branch only.
- [X] T030 [US4] (E2E executed in CI, passing) Add `TestIpPrefixTreeMapAddressPrefix` to `tests/e2e/ipam/test_ip_prefix_tree_map.py`: open 10.0.0.0/16 from the IPAM tree, click `Tree Map`, assert `get_by_test_id("ip-prefix-tree-map-empty")`, the meter, and that clicking `get_by_role("link", name="IP Addresses")` shows the addresses table; add the US2 scenario 2 test here: from 10.0.0.0/8's map click the `10.0.0.0/16` tile and assert the empty state is shown.

**Checkpoint**: US4 E2E class passes; drill-down into an address-type child lands on the empty state.

---

## Phase 7: User Story 5 - Read a very large or very fragmented prefix (Priority: P3)

**Goal**: The cap notice, the aggregated tiles and the remainder tile keep the map legible and exact.

**Independent Test**: Component and unit tests with synthetic data for the cap and the tiny-tile cases; an E2E check on the IPv6 demo prefix.

### Tests for User Story 5

- [X] T031 [P] [US5] Extend `FE/entities/ipam/ip-prefixes/domain/rules/build-tree-map-tiles.test.ts`: a /8 with three /16 children and one /32 child yields an `aggregate-allocated` tile with one member and no `allocated` tile for the /32; free blocks below `parent / 4096n` collapse into one `aggregate-free` tile; a parent with 1,000 children and `totalChildCount` 1,200 yields a `remainder` tile whose `addressCount` equals the parent minus every other tile, exactly; `2001:db8::/32` with a /48 and a /64 child aggregates both, since each is below 1/4096 of the parent (a /44 at exactly 1/4096 stays `allocated`); a /128 inside a /32 is aggregated and the sum invariant still holds; in every case no two tiles share an address range.
- [X] T032 [P] [US5] Extend `FE/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map-tile.test.tsx`: an `aggregate-allocated` tile with three members is a link named `3 smaller prefixes` whose tooltip lists the three CIDRs; an aggregate with 25 members lists 20 and "and 5 more"; a `remainder` tile is a link named `200 more children not shown`; an `aggregate-free` tile is not interactive.

### Implementation for User Story 5

- [X] T033 [US5] In `FE/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map-tile.tsx`, complete the tooltip content for the aggregate kinds (member list truncated after 20 with "and N more") and the accessible names for `aggregate-allocated`, `aggregate-free` and `remainder` per contracts/ui-contract.md. If T014 already covered them, this task is verification only.
- [X] T034 [US5] In `FE/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map.tsx::IpPrefixTreeMap`, render a `p` with `role="status"` and `text-foreground-muted` above the map reading "Showing the first <children.length> of <totalChildCount> children" when `isCapped`, formatted with the app's number formatting; add the muted swatch for aggregated tiles to the legend if T015 left it out.
- [X] T035 [US5] (E2E executed in CI, passing) Add `TestIpPrefixTreeMapIpv6` to `tests/e2e/ipam/test_ip_prefix_tree_map.py`: open `2001:db8::/100` from the IPAM tree, click `Tree Map`, assert six allocated links whose names start with `2001:db8::` and at least one free button, and assert no console errors from BigInt handling (attach a `page.on("pageerror")` listener in the test).

**Checkpoint**: All unit, component and E2E classes pass. (E2E classes were executed in CI rather than locally; all nine tests passed.)

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, changelog, measurement and the local CI gate

- [X] T036 [P] Add a "Tree Map" subsection under "## Utilization" in `docs/docs/ipam/overview.mdx` (load the `opsmill-docs:writing-infrahub-docs` skill first): two short paragraphs on what allocated, free and aggregated tiles mean, that the map shows one level and drills down on click, that free tiles open the create form, the address-type behaviour, and the 1,000-child cap. Run `uv run invoke docs.lint`.
- [X] T037 [P] Create the changelog fragment with the `creating-changelog-entries` skill (`towncrier create`, type `added`) describing the new Tree Map tab on IP prefix pages, in `changelog/`.
- [X] T038 (measured 2026-10-04: 1.86 s warm median for 256 children, passes) Run the SC-001 measurement from quickstart.md step 5 against a /16 with 256 direct /24 children on a branch and record the median in the table in `dev/specs/ifc-3300-ip-prefix-treemap/quickstart.md`. If it exceeds 3 s, open a separate issue for a batched utilisation lookup and link it from the table; do not change the backend in this feature.
- [X] T039 Run the manual theme check from quickstart.md step 4 on 10.0.0.0/8 and 2001:db8::/100 in light and dark; fix any tile that uses a non-token colour in `FE/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map-tile.tsx`.
- [X] T040 Run the frontend gates from `frontend/app/AGENTS.md` (`pnpm exec biome ci .` from `frontend/`, `pnpm knip`, `pnpm exec betterer ci`, `pnpm test` from `frontend/app/`), `uv run ruff check tests/e2e && uv run ruff format tests/e2e`, then `/pre-ci`. Fix anything red; `knip` must not report the extracted sheet or any new export as unused.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on T001 and T002; blocks every story
- **User Story 1 (Phase 3)**: Depends on Phase 2; the MVP
- **User Story 2 (Phase 4)**: Depends on US1's tile component (T014) and route (T017); otherwise independent
- **User Story 3 (Phase 5)**: Depends on US1's container (T015); the sheet extraction (T024) is independent and can start any time after Phase 2
- **User Story 4 (Phase 6)**: Depends on US1's shim (T016); its E2E also closes US2 scenario 2
- **User Story 5 (Phase 7)**: Depends on US1's rule (T012), tile (T014) and container (T015)
- **Polish (Phase 8)**: Depends on every story that ships

### Within Each User Story

- Tests are written first and fail before the implementation task that makes them pass
- Domain rules before UI components, components before the shim and route, shim and route before E2E
- The E2E module is one file shared by all stories, so its tasks are sequential across stories

### Parallel Opportunities

- Phase 1: T001 and T002 in parallel
- Phase 2: T003 and T004 in parallel with T005; T006 in parallel with T005
- US1: T009, T010 and T011 together; then T012 and T013 together; T014 after T011; T016, T017 and T018 touch different files and can run together once T015 exists
- US3: T024 (sheet extraction) in parallel with any US1 or US2 task after Phase 2
- US4: T027 and T028 together
- US5: T031 and T032 together
- Polish: T036 and T037 together

---

## Parallel Example: User Story 1

```bash
# Tests first, three files, no shared state:
Task: "T009 build-tree-map-tiles.test.ts"
Task: "T010 layout-tree-map.test.ts"
Task: "T011 ip-prefix-tree-map-tile.test.tsx"

# Then the two pure rules together:
Task: "T012 build-tree-map-tiles.ts"
Task: "T013 layout-tree-map.ts"

# Then the wiring, three different files:
Task: "T016 ipam-details-tree-map-page.tsx"
Task: "T017 router.tsx"
Task: "T018 ipam-details-layout.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 and Phase 2: model, parsing, query, use-case, hook
2. Phase 3: rules, tile, container, shim, route, tab, E2E view class
3. **STOP and VALIDATE**: open 10.0.0.0/8, compare the map against the Children tab, run the US1 tests
4. Demo-able: a read-only map with correct areas, fills and tooltips

### Incremental Delivery

1. US1 gives the read-only map (MVP)
2. US2 confirms drill-down, mostly verification since the tile already links
3. US3 adds allocation from the map and the sheet extraction
4. US4 adds the address-type empty state and closes the drill-down edge case
5. US5 adds the cap notice and verifies aggregation and the IPv6 extremes
6. Polish: docs, changelog, measurement, gates

### Parallel Team Strategy

With two developers after Phase 2: one takes US1 then US2 and US5 (the map itself); the other takes the sheet extraction (T024), US4's empty state, docs and changelog, then joins US3 wiring once US1's container exists.

---

## Notes

- Every new colour goes through a theme token; `dev/knowledge/frontend/theming.md` is the reference
- No `useEffect` is expected anywhere in this feature; the query key carries branch and date, and the sheet is plain state
- No `as` casts and no `!` assertions, including in the extracted sheet
- Commit only when asked; the git auto-commit hooks are optional and off by default in this workflow
- Each task names the file it changes; sites inside a file are referenced by symbol
