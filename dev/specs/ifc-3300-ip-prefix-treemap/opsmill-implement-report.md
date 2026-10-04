# Implementation Report: IP Prefix Tree Map

**Feature**: IP Prefix Tree Map (`dev/specs/ifc-3300-ip-prefix-treemap`)
**Branch**: `pmc/ip-prefix-treemap-viz-5dfe40f9`
**Base commit** (spec docs committed, before any code): `596f09143`
**Head commit** (last fix, before this report): `56434eeb3`
**Run**: started 2026-10-03T10:21Z, report written 2026-10-04T02:13Z. Of that span, roughly eleven hours were two stalled full-suite frontend test runs (see section 6); the nine implementation chunks took about one hour forty minutes of agent time in total.
**Status**: DONE with deferred E2E execution (no Docker daemon on the implementation machine) and the whole-suite frontend gate unverified locally. Nothing is pushed.

## 1. Chunk ledger

| # | Chunk (tasks.md phase) | Tasks | ✅ | ⚠️ | ❌ | Commit(s) | Flagged upward |
|---|------------------------|-------|----|----|----|-----------|----------------|
| 1 | Phase 1 Setup | T001, T002 | 2 | 0 | 0 | `6dab203b5` | data-model.md named the threshold constant differently from tasks.md; doc aligned in `6241191e9`. Schema-visualizer submodule had to be initialised for betterer. |
| 2 | Phase 2 Foundational | T003 to T008 | 6 | 0 | 0 | `f595ea730` | Biome forbids bitwise operators, so `2n ** BigInt(n)` replaces the shift. gql.tada types the `BigInt` scalar as `unknown`, narrowed with `typeof`. The document is imported `type`-only in the use-case so `vi.mock` can replace the api module. |
| 3 | Phase 3 US1, rules | T009 to T013 | 5 | 0 | 0 | `57f9ae30c` | Weight is plain `Number(count) / Number(parent)`; the six-digit truncation in the plan could not represent 1/256 and failed the sum invariant on the demo case. Docs aligned in `ebd75cca5`. Tie-break is children then free blocks in received order. Factories added under `tests/fake/`. |
| 4 | Phase 3 US1, UI and route | T014 to T019 | 5 | 1 (T019 E2E deferred) | 0 | `5590391a2` | `bg-subtle` is a foreground token and rendered dark grey; free tiles use `bg-content`, aggregates `bg-content-strong`. Container aspect ratio is an inline style from the shared constant (arbitrary Tailwind values are a lint error). Tooltip on a `Link` needs a react-aria `Focusable` wrapper. `aggregate-free` carries `role="img"`. Docs aligned in `315fedfc5`. Rendered against the public demo and screenshotted. |
| 5 | Phase 4 US2 | T020 to T022 | 3 | 0 (T022 E2E deferred) | 0 | `6f9cdb579` | The namespace query param is `namespace`, not `ipam-namespace`; spec docs corrected in `c27129c06`. Schema seeded in the component test so the `/ipam/` URL family is exercised. |
| 6 | Phase 5 US3 | T023 to T026 | 4 | 0 (T026 E2E deferred) | 0 | `dce900084` | Extracted `IpPrefixCreateSheet`; the identifier's `kind!` assertion is gone. Disabled free tiles expose `aria-disabled`, which Playwright's `to_be_disabled()` honours. |
| 7 | Phase 6 US4 | T027 to T030 | 4 | 0 (T030 E2E deferred) | 0 | `d0b255515` | The empty-state link must be parent-relative (`../ip_addresses`) because it renders inside the `tree-map` child route; contract corrected in `8a9a594f4`. Shim is 33 lines against a 30-line target. |
| 8 | Phase 7 US5 | T031 to T035 | 5 | 0 (T035 E2E deferred) | 0 | `d78622cd2` | tasks.md T031 wording contradicted research R5: a /48 in a /32 is below 1/4096 and is aggregated; spec scenario 4 allows it. A boundary test proves a /44 stays allocated. Use-case mocked instead of the hook to avoid casts. |
| 9 | Phase 8 Polish | T036 to T040 | 4 | 1 (T040 whole-suite gate not completed locally) | 0 | `febfd9506`, `53073e525` | SC-001 measurement deferred (needs Docker). Light and dark screenshots taken for 10.0.0.0/8 and 2001:db8::/100; no non-token colours found. The agent's full-suite run stalled; the orchestrator took the gate over (section 6). |
| R | Review fixes | from section 5 | n/a | | | `56434eeb3` | See section 5. |

## 2. Tasks not completed

None. All forty tasks are `[X]` in `tasks.md`. Two carry explicit deferrals recorded in their artefacts: T038 (SC-001 measurement, table row marked deferred in `quickstart.md`) and the E2E execution of T019, T022, T026, T030 and T035 (section 4).

## 3. Local-pass evidence

Every unit and component test below was observed passing in the final run after the review fixes:

- Command: `cd frontend/app && pnpm vitest run src/entities/ipam src/pages/ipam`
- Passed at: 2026-10-04T01:53:34Z
- Environment: Vitest 4.1.10 browser mode, Playwright 1.60.0, Chrome Headless Shell 148 (chromium_headless_shell-1223), macOS arm64, Node 26.8.2
- Summary line: `Test Files  8 passed (8)` / `Tests  93 passed (93)` / `Duration  4.82s`

Per-test verbatim pass lines come from the verbose runs each chunk reported (timestamps in the Passed-at column); the final run above re-executed all of them.

| Test id | Type | Run command | Passed at (ISO 8601) | Environment context | Verbatim pass line |
|---------|------|-------------|----------------------|---------------------|--------------------|
| `domain/rules/parse-prefix-length.test.ts > parsePrefixLength > parses an IPv4 prefix into its family, length and address count` | unit | `cd frontend/app && pnpm vitest run src/entities/ipam/ip-prefixes --reporter=verbose` | 2026-10-03T10:30:39Z | vitest browser mode, chromium | `✓ \|chromium\| … > parses an IPv4 prefix into its family, length and address count 1ms` |
| `… > parses an IPv6 prefix into its family, length and address count` | unit | same | 2026-10-03T10:30:39Z | same | `✓ \|chromium\| … 0ms` |
| `… > gives the full IPv6 space for a zero-length prefix` | unit | same | 2026-10-03T10:30:39Z | same | `✓ \|chromium\| … 0ms` |
| `… > gives the full IPv4 space for a zero-length prefix` | unit | same | 2026-10-03T10:30:39Z | same | `✓ \|chromium\| … 0ms` |
| `… > throws when an IPv4 prefix length exceeds 32` | unit | same | 2026-10-03T10:30:39Z | same | `✓ \|chromium\| … 1ms` |
| `… > throws when an IPv6 prefix length exceeds 128` | unit | same | 2026-10-03T10:30:39Z | same | `✓ \|chromium\| … 0ms` |
| `… > throws when the string has no slash` | unit | same | 2026-10-03T10:30:39Z | same | `✓ \|chromium\| … 0ms` |
| `… > throws when the string is empty` | unit | same | 2026-10-03T10:30:39Z | same | `✓ \|chromium\| … 0ms` |
| `domain/use-cases/get-ip-prefix-tree-map.test.ts > getIpPrefixTreeMap > maps real nodes to children in address order with the matching member count` | unit | same | 2026-10-03T10:30:39Z | same | `✓ \|chromium\| … 1ms` |
| `… > maps available nodes to free blocks parsed from their prefix value` | unit | same | 2026-10-03T10:30:39Z | same | `✓ \|chromium\| … 0ms` |
| `… > reports the query count as the total child count and is not capped when it matches` | unit | same | 2026-10-03T10:30:39Z | same | `✓ \|chromium\| … 0ms` |
| `… > drops a node whose prefix value is null` (now also asserts `isCapped` false) | unit | final run | 2026-10-04T01:53:34Z | same | `Tests  93 passed (93)` |
| `… > is capped when the count exceeds the real children returned` | unit | same | 2026-10-03T10:30:39Z | same | `✓ \|chromium\| … 0ms` |
| `… > passes the parent id, limit, branch and date through to the api` | unit | same | 2026-10-03T10:30:39Z | same | `✓ \|chromium\| … 0ms` |
| `… > rejects with the messages of the errors the api returned` | unit | same | 2026-10-03T10:30:39Z | same | `✓ \|chromium\| … 1ms` |
| `domain/rules/build-tree-map-tiles.test.ts > buildTreeMapTiles > produces one tile per child and free block of the demo /8` | unit | `cd frontend/app && pnpm vitest run src/entities/ipam/ip-prefixes --reporter=verbose` | 2026-10-03T10:39:42Z | same | `✓ \|chromium\| … > produces one tile per child and free block of the demo /8 1ms` |
| `… > sums the tile address counts exactly to the parent's address count` | unit | same | 2026-10-03T10:39:42Z | same | `✓ \|chromium\| … 0ms` |
| `… > sums the tile weights to one` | unit | same | 2026-10-03T10:39:42Z | same | `✓ \|chromium\| … 0ms` |
| `… > produces no free tile for a fully allocated parent` | unit | same | 2026-10-03T10:39:42Z | same | `✓ \|chromium\| … 0ms` |
| `… > produces two free tiles for an empty parent split into two halves` | unit | same | 2026-10-03T10:39:42Z | same | `✓ \|chromium\| … 0ms` |
| `… > keeps a null utilization on the allocated tile` | unit | same | 2026-10-03T10:39:42Z | same | `✓ \|chromium\| … 0ms` |
| `… > sorts tiles by weight descending and keeps ties in the received address order` | unit | same | 2026-10-03T10:39:42Z | same | `✓ \|chromium\| … 0ms` |
| `… > uses the parent's exact address count for IPv6 weights` | unit | same | 2026-10-03T10:39:42Z | same | `✓ \|chromium\| … 0ms` |
| `… > aggregates a /32 child of a /8 into a one-member smaller-prefixes tile` | unit | `cd frontend/app && pnpm vitest run src/entities/ipam src/pages/ipam --reporter=verbose` | 2026-10-03T17:15:08Z | same | `✓ \|chromium\| … 0ms` |
| `… > collapses free blocks below 1/4096 of the parent into one smaller-free-blocks tile` | unit | same | 2026-10-03T17:15:08Z | same | `✓ \|chromium\| … 0ms` |
| `… > sizes the remainder tile to the parent minus every other tile when children are capped` | unit | same | 2026-10-03T17:15:08Z | same | `✓ \|chromium\| … 9ms` |
| `… > aggregates both a /48 and a /64 inside an IPv6 /32 as they fall below 1/4096` | unit | same | 2026-10-03T17:15:08Z | same | `✓ \|chromium\| … 0ms` |
| `… > keeps an IPv6 child exactly at 1/4096 of its parent as an allocated tile` | unit | same | 2026-10-03T17:15:08Z | same | `✓ \|chromium\| … 0ms` |
| `… > aggregates a /128 inside a /32 while the address counts still sum to the parent` | unit | same | 2026-10-03T17:15:08Z | same | `✓ \|chromium\| … 1ms` |
| `domain/rules/layout-tree-map.test.ts > layoutTreeMap at aspect ratio {1,2} > keeps every rect inside the container for {3 cases}` (6 tests) | unit | `… src/entities/ipam/ip-prefixes --reporter=verbose` | 2026-10-03T10:39:42Z | same | `✓ \|chromium\| … > layoutTreeMap at aspect ratio 1 > keeps every rect inside the container for 'weights 0.5, 0.25 and 0.25' 1ms` and 5 siblings |
| `… > never overlaps two rects for {3 cases} x {1,2}` (6 tests) | unit | same | 2026-10-03T10:39:42Z | same | `✓ \|chromium\| … never overlaps two rects for 'weights 0.5, 0.25 and 0.25' 0ms` and 5 siblings |
| `… > sizes each rect's area to its tile weight for {3 cases} x {1,2}` (6 tests) | unit | same | 2026-10-03T10:39:42Z | same | `✓ \|chromium\| … sizes each rect's area to its tile weight for 'weights 0.5, 0.25 and 0.25' 0ms` and 5 siblings |
| `… > returns one rect per tile in the input order for {3 cases} x {1,2}` (6 tests) | unit | same | 2026-10-03T10:39:42Z | same | `✓ \|chromium\| … returns one rect per tile in the input order for 'weights 0.5, 0.25 and 0.25' 0ms` and 5 siblings |
| `… > layoutTreeMap > returns no rects for no tiles` | unit | same | 2026-10-03T10:39:42Z | same | `✓ \|chromium\| … 0ms` |
| `… > gives a zero-weight tile a zero-size rect` | unit | same | 2026-10-03T10:39:42Z | same | `✓ \|chromium\| … 0ms` |
| `… > splits two equal tiles across the longer side of a 2:1 container` | unit | same | 2026-10-03T10:39:42Z | same | `✓ \|chromium\| … 0ms` |
| `ui/ip-prefix-tree-map-tile.test.tsx > IpPrefixTreeMapTile > names an allocated tile at {0,50,100} percent utilised` (3 tests) | component | `cd frontend/app && pnpm vitest run src/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map-tile.test.tsx --reporter=verbose` | 2026-10-03T11:02:27Z | same | `✓ \|chromium\| … IpPrefixTreeMapTile > …` × 14, `Tests  14 passed (14)` |
| `… > fills an allocated tile to {0,50,100} percent of its width` (3 tests) | component | same | 2026-10-03T11:02:27Z | same | same run |
| `… > names an allocated tile with unknown utilisation` | component | same | 2026-10-03T11:02:27Z | same | same run |
| `… > renders no fill when the utilisation is unknown` | component | same | 2026-10-03T11:02:27Z | same | same run |
| `… > exposes a free tile as a button named with its CIDR` | component | same | 2026-10-03T11:02:27Z | same | same run |
| `… > marks a <kind> tile with its test id and tile kind` (5 tests) | component | same | 2026-10-03T11:02:27Z | same | same run |
| `… > links an allocated tile to the child's tree map in the current namespace` | component | `… src/entities/ipam/ip-prefixes --reporter=verbose` | 2026-10-03T16:49:38Z | same | `✓ \|chromium\| … links an allocated tile to the child's tree map in the current namespace 23ms` |
| `… > links an aggregate tile to the parent's children in the current namespace` | component | same | 2026-10-03T16:49:38Z | same | `✓ \|chromium\| … 4ms` |
| `… > calls the create handler with the free block when its button is clicked` | component | `… src/entities/ipam --reporter=verbose` | 2026-10-03T16:56:15Z | same | `✓ … 72ms` |
| `… > disables the free tile button when creating prefixes is not allowed` | component | same | 2026-10-03T16:56:15Z | same | `✓ … 3ms` |
| `… > does not call the create handler from a disabled free tile` | component | same | 2026-10-03T16:56:15Z | same | `✓ … 13ms` |
| `… > shows the permission message when hovering a disabled free tile` | component | same | 2026-10-03T16:56:15Z | same | `✓ … 292ms` |
| `… > names an aggregate of three allocated prefixes as a link` | component | `… src/entities/ipam src/pages/ipam --reporter=verbose` | 2026-10-03T17:15:08Z | same | `✓ \|chromium\| … 2ms` |
| `… > lists the member CIDRs when hovering an aggregate of three allocated prefixes` | component | same | 2026-10-03T17:15:08Z | same | `✓ \|chromium\| … 72ms` |
| `… > truncates the member list after twenty CIDRs when hovering a large aggregate` | component | same | 2026-10-03T17:15:08Z | same | `✓ \|chromium\| … 74ms` |
| `… > names a remainder tile after the children it does not show` | component | same | 2026-10-03T17:15:08Z | same | `✓ \|chromium\| … 2ms` |
| `… > exposes an aggregate of free blocks as a non-interactive image` | component | same | 2026-10-03T17:15:08Z | same | `✓ \|chromium\| … 1ms` |
| `… > keeps the branch and namespace params on an allocated tile's link` (review fix) | component | `cd frontend/app && pnpm vitest run src/entities/ipam src/pages/ipam` | 2026-10-04T01:53:34Z | same | `Tests  93 passed (93)` |
| `… > shows the child's details when hovering an allocated tile` (review fix) | component | same | 2026-10-04T01:53:34Z | same | `Tests  93 passed (93)` |
| `… > shows the CIDR when hovering a free tile` (review fix) | component | same | 2026-10-04T01:53:34Z | same | `Tests  93 passed (93)` |
| `ui/ip-prefix-tree-map-empty-state.test.tsx > IpPrefixTreeMapEmptyState > shows the utilisation meter, the explanation and the IP Addresses link` | component | `… src/entities/ipam src/pages/ipam --reporter=verbose` | 2026-10-03T17:03:42Z | same | `✓ … 25ms` |
| `… > shows the explanation and the link without a meter when utilisation is unknown` | component | same | 2026-10-03T17:03:42Z | same | `✓ … 3ms` |
| `… > links to the sibling IP Addresses tab in the current namespace from the tree map route` | component | same | 2026-10-03T17:03:42Z | same | `✓ … 4ms` |
| `ui/ip-prefix-tree-map.test.tsx > announces how many children are shown when the parent has more than the cap` | component | same | 2026-10-03T17:15:08Z | same | `✓ \|chromium\| … 226ms` |
| `… > shows no cap notice when every child fits in the map` | component | same | 2026-10-03T17:15:08Z | same | `✓ \|chromium\| … 65ms` |
| `tests/e2e/ipam/test_ip_prefix_tree_map.py::TestIpPrefixTreeMapView::test_shows_allocated_and_free_tiles` | e2e | `uv run pytest -c tests/e2e/pytest.ini tests/e2e/ipam/test_ip_prefix_tree_map.py` | deferred — local E2E not supported | no Docker daemon on the implementation machine; collected with `--collect-only` (`9 tests collected`) | n/a |
| `…::TestIpPrefixTreeMapView::test_shows_legend` | e2e | same | deferred — local E2E not supported | same | n/a |
| `…::TestIpPrefixTreeMapDrillDown::test_child_tile_opens_child_tree_map_in_same_namespace` | e2e | same | deferred — local E2E not supported | same | n/a |
| `…::TestIpPrefixTreeMapBranch::test_branch_only_child_appears_on_its_branch_only` | e2e | same | deferred — local E2E not supported | same | n/a |
| `…::TestIpPrefixTreeMapCreate::test_free_tile_creates_prefix_and_map_refreshes` | e2e | same | deferred — local E2E not supported | same | n/a |
| `…::TestIpPrefixTreeMapCreate::test_free_tile_is_disabled_for_read_only_user` | e2e | same | deferred — local E2E not supported | same | n/a |
| `…::TestIpPrefixTreeMapAddressPrefix::test_shows_empty_state_with_meter_and_link_to_addresses` | e2e | same | deferred — local E2E not supported | same | n/a |
| `…::TestIpPrefixTreeMapAddressPrefix::test_drill_down_into_address_prefix_shows_empty_state` | e2e | same | deferred — local E2E not supported | same | n/a |
| `…::TestIpPrefixTreeMapIpv6::test_shows_ipv6_children_and_free_blocks_without_page_errors` | e2e | same | deferred — local E2E not supported | same | n/a |

The E2E module was lint-checked (`uv run ruff check tests/e2e && uv run ruff format tests/e2e`, clean) and collected after the review fix at 2026-10-04T01:53:34Z. The Children-tab regression E2E `tests/e2e/ipam/test_ip_prefix_create.py` is also deferred for the same reason.

Other gates at head: `cd frontend && pnpm exec biome ci .` clean (1614 files); `cd frontend/app && pnpm exec betterer ci` unchanged (176 baseline issues); `cd frontend/app && pnpm knip` clean apart from a pre-existing config hint; markdownlint on the spec documents and `docs/docs/ipam/overview.mdx` clean; `uv run invoke docs.validate` reported no stale generated doc (chunk 9).

## 4. Whole-suite frontend gate

`pnpm test` (the full Vitest browser-mode suite) could not be completed on this machine:

- First full run (chunk 9): `Test Files 15 failed | 199 passed (220)`, `Tests 38 failed | 1411 passed (1449)`, `Duration 28797s`. The tests themselves took 138 s; the rest was a stall. Every failure followed a Vite "optimized dependencies changed. reloading" message and reads `Vitest failed to find the runner`, the documented cold-cache flake (`changelog/+frontend-tests-optimizedeps-reload-flake.housekeeping.md`). The discovered dependencies were `@tanstack/react-table`, `zod`, `nuqs/adapters/testing`, `@xyflow/react`, `@radix-ui/react-accordion`; none is touched by this feature.
- The 15 failed files rerun in isolation with a warm cache: `Test Files 15 passed (15)`, `Tests 194 passed (194)` at 2026-10-04T01:42:18Z.
- Second full run with a 30 minute cap: reloaded twice at startup and produced no summary before the cap (`exit 124`).

CI runs `pnpm test` on a clean install in the `frontend-tests` job; that is where the whole-suite result must be read.

## 5. Review findings

Five read-only reviewers ran over `596f09143..HEAD` (code, tests, comments, error handling, types). No finding was rated critical. "Important" findings and what happened to them:

| Severity | Reviewer | File | Summary | Outcome |
|----------|----------|------|---------|---------|
| important | errors | `domain/use-cases/get-ip-prefix-tree-map.ts` | A node dropped for an unparseable CIDR was counted as "beyond the cap", producing a false cap notice and remainder tile | Fixed in `56434eeb3`: dropped nodes are counted separately, logged with `console.warn`, and excluded from the cap arithmetic; the drop test now asserts `isCapped` is false |
| important | errors | same | A missing page in the response rendered an empty map silently | Fixed: throws, surfacing `ErrorScreen` |
| important | types | same and `domain/rules/get-tree-map-parent.ts` | `member_type` fell back to `"prefix"` for any unexpected value | Fixed: unknown member type rejects the node (use-case) or returns `null` (parent rule, shown as the existing error screen) |
| important | tests | `tests/e2e/ipam/test_ip_prefix_tree_map.py` | Four tests indexed the data fixture handle for the supernet id, which is empty when the suite runs against an external instance | Fixed: a module-level `supernet_id` fixture resolves it through the SDK client; the `branch` fixture is shared too; exact `0% utilised` names replaced by CIDR-prefix regexes |
| important | tests | `ui/ip-prefix-tree-map-tile.test.tsx` | No test covered the allocated or free tile hover details (FR-005), nor branch preservation in the drill-down link (FR-007) | Fixed: three tests added |
| important | comments | `domain/rules/build-tree-map-tiles.ts` | Comment claimed the weight division is exact for every tile | Fixed: states that only aggregate and remainder weights carry rounding |
| important | comments | `data-model.md`, `research.md`, `ui-contract.md`, fake factory docstring, `overview.mdx` | Stale formula, a validation clause the code does not implement, border and label wording, "subtle surface", "1,024 at most", unconditional meter | Fixed in `56434eeb3` |
| important | code | `ui/ip-prefix-tree-map-tile.tsx` | Fill colour is an inline `color-mix(...)` style; `styling.md` lists inline colours as a Don't (the percentage geometry is legitimately inline) | Deferred: the fix is a new theme token (`:root`, `.dark`, `@theme inline`) in the shared UI package, which is a cross-cutting edit; the in-repo precedent `multiple-progress-bar.tsx` uses the same inline pattern |
| important | types | `domain/model/ip-prefix-tree-map.ts` | `kind: string` on child and parent where the GraphQL `__typename` is a literal union; `IP_PREFIX_AVAILABLE_KIND` is not `as const` | Deferred: type tightening with no behavioural effect |
| important | types | same | Invariants (weight 0..1, counts sum) live in the rule and its tests, not in the types | Deferred by design; a branded type was judged overkill |

Suggestions recorded, not acted on: `role="img"` on the free aggregate makes its member list mouse-only (keyboard users can still read the accessible name); spelling mix between "utilised" in tile names and "Utilization" elsewhere in the tab (a product-copy decision, see section 6); the create sheet's three-way optional `prefix` prop; the dead `if (errors)` branch in the use-case (the client throws before returning errors); a FR-006 label-visibility test and loading/error state tests for the container; the E2E branch fixtures' `contextlib.suppress(Exception)` on delete, which matches the repo-wide convention; the 226-line tile file against a 150-line soft budget.

The `simplify` reviewer, enabled in the review config, was not run: it applies code changes rather than reporting, and the five review passes had already produced the fixes above.

## 6. Autonomous decisions

- **Commits per chunk.** Confirmed with the user before the run started. The spec documents were committed first (`596f09143`) so the review diff covers code only. No push, no PR.
- **Pre-specify hook skipped.** The repo's hook requires a Jira or JPD ticket in the branch name; none exists. The worktree branch name was kept.
- **Chunking.** User Story 1 was split into rules (chunk 3) and UI plus route (chunk 4); every other phase was one chunk. The tile component test was written in chunk 3 against a stated props contract and made to pass in chunk 4.
- **Spec deviations accepted from subagents** and reflected back into the spec documents in the same run: exact float weights instead of six-digit truncation; `bg-content`/`bg-content-strong` instead of `bg-subtle`/`bg-content-muted`; an inline aspect ratio from the shared constant; `role="img"` on the free aggregate; the parent-relative IP Addresses link; the `namespace` query parameter name; the /48-in-a-/32 aggregation.
- **E2E execution deferred.** Docker is not running on the implementation machine. All nine E2E tests were written, lint-checked and collected; none was executed. CI command: `uv run pytest -c tests/e2e/pytest.ini tests/e2e/ipam/test_ip_prefix_tree_map.py`.
- **SC-001 measurement deferred.** It needs a stack with Docker and the demo data; writing 256 prefixes to the public demo instance was ruled out.
- **Whole-suite gate taken over from the chunk 9 agent** after its first run stalled for eight hours and it started a second one. The second run was killed, the fifteen failed files were rerun in isolation (all pass), and one more capped full run was attempted (stalled). Recorded in section 4 rather than treated as a regression.
- **Review fixes applied by the orchestrator** rather than a subagent: all were small and localised (one use-case, one rule, one comment, test additions, doc sentences). The inline-colour token change was deferred because it edits the shared theme file.
- **Spelling of the tile names.** The contract specified "utilised" and the product UI uses "Utilization". Changing it touches accessible names in component and E2E tests and the contract; left for the user to decide.

## 7. Suggested next steps

1. Run the full frontend suite in CI (`frontend-tests` job) or on a machine where `pnpm test` completes, and read the whole-suite result there; the stall is environmental, not a product bug, but it is unverified here.
2. Run the E2E module on a Docker-capable machine against the image built from this branch: `uv run invoke dev.build && INFRAHUB_TESTING_IMAGE_VER=local INFRAHUB_TESTING_DOCKER_PULL=false uv run pytest -c tests/e2e/pytest.ini tests/e2e/ipam/test_ip_prefix_tree_map.py -s --pdb`, plus `tests/e2e/ipam/test_ip_prefix_create.py` for the Children-tab refactor.
3. Take the SC-001 measurement (quickstart.md step 5) and fill the table; if it exceeds 3 s, raise a separate gated change for a batched utilisation lookup.
4. Decide on "utilised" versus "utilized" in the tile names, and on the inline fill colour versus a new `--accent-fill` theme token.
5. Attach a JPD or Jira ticket, rename the branch to `ip-prefix-treemap-<ticket>` if the hook convention matters, and open the PR as a draft.

## Erratum (2026-10-04, after the report above)

Both product decisions in section 6 were put to the user and resolved in the commit that follows this report:

- **Spelling**: American. Tile names and tooltips now read `"<CIDR>, <N>% utilized"` and `"<CIDR>, utilization unknown"`; the component tests, the E2E helper docstring and `contracts/ui-contract.md` were updated to match. The E2E locators already matched on the CIDR prefix, so no E2E assertion changed.
- **Fill colour**: a theme token. `--accent-fill` is declared in `frontend/packages/ui/src/styles/theme.css` for `:root` and `.dark` as a 55% alpha of `--accent-strong`, bridged through `@theme inline`, and used as `bg-accent-fill` on the tile fill and the legend swatch. The only inline style left on the fill is its data-driven width. Verified against the public demo through the local dev server: the computed fill is `oklab(… / 0.55)` derived from the light accent in light mode and from the dark accent in dark mode. Gates after the change: 93 IPAM tests pass, Biome, betterer, knip, ruff and markdownlint clean.

Next step 4 above is therefore closed.

## Erratum 2 (2026-10-04, after loading the infrahub-demo-dc dataset locally)

The feature was exercised against a dev-stack build of this branch with the `infrahub-demo-dc`
bootstrap and Arista data centre loaded. Every prefix in that dataset carries `member_type:
address`, including supernets with child prefixes (10.0.0.0/8 with five children, 0.0.0.0/0 with
five children and eighteen descendants), so under FR-010 as originally written the map never
rendered: every page showed the empty state. The user chose to decide from the data instead of the
member type. The query now runs for every prefix; the container renders the empty state only when
the parent is address-type and the query returned no child prefixes, and the map otherwise. FR-010,
User Story 4, the UI contract, the user docs and the container tests were updated (95 tests pass),
and the map was confirmed rendering on 10.0.0.0/8 and 0.0.0.0/0 on `main` and on 10.0.0.0/8 on
the `add-dc3` branch through the dev server against the local stack.

## Erratum 3 (2026-10-04, IPAM tree sidebar follows navigation)

Drilling down from a tile left the IPAM tree sidebar unchanged: the parent stayed collapsed and the
new prefix was not highlighted. The same happened when clicking a child in the Children table, so
this was a pre-existing limitation of the sidebar that drill-down made constant. The tree loaded
ancestors only for the prefix present when it first mounted and used them as the initial expanded
keys. The user chose to fix it on this branch. The tree now loads ancestors for the current prefix
on every change (keeping the previous data while the next loads), and its expansion is controlled:
the expanded set is derived during render as the current ancestor path merged with the user's
manual toggles, where a manual collapse is honoured only for the prefix it was made on. The
derivation lives in a pure rule under `entities/ipam/ipam-tree/domain/rules/` with eight unit tests;
the drill-down E2E test now also asserts the sidebar row is selected. Verified on the local stack
for both the Children table and the Tree Map paths (103 frontend tests pass).

## Erratum 4 (2026-10-04, visual encoding after hands-on review)

Reviewing the map on the demo data, the user found allocated and free tiles too similar, wanted
descriptions visible on tiles, and asked for pools to be told apart from static allocations.
Changes: free tiles now carry a diagonal hatch (a `tree-map-hatch` utility drawn from
`--border-strong`) on top of the dashed border; allocated tiles have a solid accent border; prefixes
with `is_pool` use a new `pool` token family (fuchsia, declared for both themes in the shared
theme) for surface, border and fill, with a "Pool" legend entry and a "Prefix pool" tooltip line;
an allocated tile shows its description on a second line from 11rem wide and otherwise a small
marker next to the CIDR, the tooltip always carrying the full text. The query selects `is_pool`,
the child model carries `isPool`, and FR-004 gained the pool colour and a new FR-004a for the
description. Verified on 10.0.0.0/8 of the `add-dc3` branch in both themes (106 frontend tests
pass).

## Erratum 5 (2026-10-04, E2E results from CI)

The nine E2E tests deferred in section 4 ran in the pull request's `E2E-testing-pytest-playwright
(foundation)` shard. The first run failed on every allocated-tile locator: Playwright 1.60 does not
escape `/` inside a regex embedded in a selector, so the CIDR patterns ended the selector early.
The CI monitor reproduced it locally against an image built from the branch, escaped the slashes in
the selector helper, and corrected one expectation (on `main` the free space below 10.0.0.0/8
aggregates to 10.4.0.0/14, so no `10.5.0.0/16 available` tile exists). After that fix the module
passed 9/9 in CI on three consecutive runs, and every other non-skipped job was green. The SC-001
measurement is recorded in quickstart.md.

## Erratum 6 (2026-10-04, rework after review)

A review of the first implementation asked for five changes, all made on the branch before the PR
left draft:

- **Layout**: the squarified algorithm was replaced by an address-ordered layout along a Hilbert
  curve (research R3). Blocks consecutive in address space now share an edge, so a run of free
  blocks reads as one region. Binary partition and Z-order were considered and rejected because
  consecutive blocks separate at alternate levels. Tiles are no longer sorted by size.
- **Aggregation and the cap**: small blocks aggregate per `/(parent + 12)` cell and the aggregate
  sits where its cell sits (research R5, `TREE_MAP_CELL_DEPTH`). The "remainder" tile is gone; when
  the map is capped, the range from the end of the last fetched block to the end of the parent is
  decomposed into aligned CIDR blocks drawn as **Not loaded** with a cross-hatch, never as free or
  allocated, with a legend entry and a notice that says so.
- **Prefix size from the API**: `prefixlen` and `version` are selected on every prefix (and on the
  parent through an aliased root field in the same document); only the network address is parsed,
  into a `BigInt`. `parse-prefix-length.ts` and `get-tree-map-parent.ts` were deleted and
  `prefix-size.ts` added. `num_addresses` is not used because it is a 32-bit `Int`.
- **Tokens**: `--accent-fill` and the `--pool` family moved out of `@infrahub/ui`'s `theme.css`
  into the app stylesheet `frontend/app/src/app/styles/index.css`, alongside the hatch utilities.
  The utility classes resolve exactly as before; nothing in the shared package changed.
- **Sidebar fix split out**: the IPAM tree change recorded in Erratum 3 left this branch and is
  its own change (#10866, PR #10871), with its changelog fragment and a new E2E test that
  navigates from the Children table. The drill-down E2E test here no longer asserts the sidebar.

The spec (FR-002a, FR-011, FR-012, new assumption, out of scope), plan, research, data model,
contracts and quickstart were updated to the current design in the same commit; the task
descriptions above keep their original wording and carry a rework note at the top. The docs guide
and its screenshot were regenerated for the new layout. Gates after the rework: 79 IPAM unit and
component tests pass, the full frontend suite passes (220 files, 1,678 tests), and Biome, knip,
betterer, ruff, ty and markdownlint are clean.
