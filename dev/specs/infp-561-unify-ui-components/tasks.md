# Tasks: Unify UI Components with react-aria-components

**Input**: Design documents from `/specs/infp-561-unify-ui-components/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Unit tests for NEW components only (aria/button, aria/badge, aria/tabs, aria/accordion). No test tasks for consumer migration (existing E2E tests validate behavior).

**Organization**: Tasks are grouped by user story to enable independent implementation. Each story corresponds to one or more PRs following the hard-cut migration strategy.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

All paths relative to `frontend/app/src/shared/components/` unless noted otherwise.

---

## Phase 1: Setup

**Purpose**: Verify existing aria/ patterns and establish migration conventions

- [ ] T001 Audit existing aria/ component patterns — read `aria/style-rac.ts`, `aria/tooltip.tsx`, `aria/breadcrumbs.tsx` to catalog shared style tokens (focusVisibleStyle, disabledStyle) and composeRenderProps usage in `frontend/app/src/shared/components/aria/`
- [ ] T002 Verify Pill and BadgeCircle consumer counts — grep for imports of `display/pill` and `display/badge-circle` across `frontend/app/src/` to confirm if they are unused and can be safely deleted

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No blocking foundational tasks for this feature. All aria/ infrastructure (style-rac.ts, composeRenderProps patterns, stacked modal utility) already exists.

**Checkpoint**: Foundation ready — user story implementation can begin.

---

## Phase 3: User Story 1 — Consolidate Selection and Action Components (Priority: P1)

**Goal**: Migrate Radix DropdownMenu → aria/menu (8 consumers), cmdk Combobox → aria/autocomplete (35 consumers), and checkbox (4 consumers). Select, ListBox, and Autocomplete already exist in aria/.

**Independent Test**: All action menus, searchable dropdowns, and checkboxes use react-aria components from `aria/`. No imports from `ui/dropdown-menu`, `ui/combobox`, `ui/command`, or `inputs/checkbox` remain.

### Implementation for User Story 1

**PR 3: Menu Migration (8 consumers)**

- [ ] T003 [US1] Read `ui/dropdown-menu.tsx` and `aria/menu.tsx` to map Radix DropdownMenu API to react-aria Menu API in `frontend/app/src/shared/components/`
- [ ] T004 [US1] Update all 8 consumers of `ui/dropdown-menu` to import from `aria/menu` — adapt DropdownMenuTrigger→MenuTrigger, DropdownMenuItem→MenuItem, DropdownMenuSeparator→MenuSection patterns across `frontend/app/src/`
- [ ] T005 [US1] Delete `ui/dropdown-menu.tsx` and `ui/accordion.tsx` (its only consumer was dropdown-menu) in `frontend/app/src/shared/components/ui/`
- [ ] T006 [US1] Run `pnpm build && pnpm test && pnpm biome:fix` to verify Menu migration in `frontend/app/`

**PR 7: Combobox/cmdk → Autocomplete (35 consumers)**

- [ ] T007 [US1] Read `ui/combobox.tsx` and `ui/command.tsx` to map cmdk Command API to react-aria Autocomplete API — document prop mapping in `frontend/app/src/shared/components/`
- [ ] T008 [US1] Update all 35 consumers of `ui/combobox` to import from `aria/autocomplete` — adapt CommandInput→AutocompleteSearchField, CommandList→ListBox, CommandItem→ListBoxItem patterns across `frontend/app/src/`
- [ ] T009 [US1] Delete `ui/combobox.tsx` and `ui/command.tsx` in `frontend/app/src/shared/components/ui/`
- [ ] T010 [US1] Remove `cmdk` from `frontend/app/package.json` dependencies
- [ ] T011 [US1] Run `pnpm install && pnpm build && pnpm test && pnpm biome:fix` to verify Autocomplete migration in `frontend/app/`

**PR 4: Checkbox Migration (4 consumers)**

- [ ] T012 [P] [US1] Update all 4 consumers of `inputs/checkbox` to import from `aria/checkbox` — adapt native checkbox props to react-aria Checkbox API across `frontend/app/src/`
- [ ] T013 [P] [US1] Delete `inputs/checkbox.tsx` in `frontend/app/src/shared/components/inputs/`
- [ ] T014 [US1] Run `pnpm build && pnpm test && pnpm biome:fix` to verify Checkbox migration in `frontend/app/`

**Checkpoint**: All selection/action components use react-aria. No Radix DropdownMenu, cmdk, or native checkbox imports remain.

---

## Phase 4: User Story 2 — Consistent Tooltip/Popover Overlays (Priority: P1)

**Goal**: Migrate all 41 Radix Tooltip consumers and 29 Radix Popover consumers to existing react-aria equivalents.

**Independent Test**: No imports from `ui/tooltip` or `ui/popover` remain. All tooltips and popovers render with consistent styling from `aria/tooltip.tsx` and `aria/popover.tsx`.

### Implementation for User Story 2

**PR 1: Tooltip Migration (41 consumers)**

- [ ] T015 [US2] Read `ui/tooltip.tsx` and `aria/tooltip.tsx` to map Radix Tooltip API (TooltipProvider, TooltipTrigger, TooltipContent) to react-aria Tooltip API (TooltipTrigger, Tooltip) in `frontend/app/src/shared/components/`
- [ ] T016 [US2] Update all 41 consumers of `ui/tooltip` to import from `aria/tooltip` — adapt TooltipProvider removal, TooltipContent→Tooltip, prop differences across `frontend/app/src/`
- [ ] T017 [US2] Delete `ui/tooltip.tsx` in `frontend/app/src/shared/components/ui/`
- [ ] T018 [US2] Run `pnpm build && pnpm test && pnpm biome:fix` to verify Tooltip migration in `frontend/app/`

**PR 2: Popover Migration (29 consumers)**

- [ ] T019 [US2] Read `ui/popover.tsx` and `aria/popover.tsx` to map Radix Popover API (PopoverTrigger, PopoverContent, PopoverTabs) to react-aria Popover API (PopoverTrigger, Popover, PopoverDialog) in `frontend/app/src/shared/components/`
- [ ] T020 [US2] Update all 29 consumers of `ui/popover` to import from `aria/popover` — handle PopoverTabs migration (may need to compose Tabs+Popover) across `frontend/app/src/`
- [ ] T021 [US2] Delete `ui/popover.tsx` in `frontend/app/src/shared/components/ui/`
- [ ] T022 [US2] Run `pnpm build && pnpm test && pnpm biome:fix` to verify Popover migration in `frontend/app/`

**Checkpoint**: All tooltips and popovers render from react-aria components with consistent visual design.

---

## Phase 5: User Story 3 — Unified Button System (Priority: P2)

**Goal**: Create `aria/button.tsx` with CVA variants matching current ui/button API, migrate 120 consumers, and absorb specialized button components.

**Independent Test**: All buttons across the app import from `aria/button`. No imports from `ui/button` or `buttons/` remain.

### Implementation for User Story 3

**PR 5: Button (120 consumers)**

- [ ] T023 [US3] Read `ui/button.tsx` to extract all CVA variants, sizes, and composed components (ButtonWithTooltip, LinkButton) in `frontend/app/src/shared/components/ui/button.tsx`
- [ ] T024 [US3] Create `aria/button.tsx` wrapping react-aria Button with CVA variants (primary, primary-outline, danger, warning, active, active-outline, outline, dark, ghost) and sizes (default, sm, icon, square) — use composeRenderProps and style-rac tokens in `frontend/app/src/shared/components/aria/button.tsx`
- [ ] T025 [US3] Create `aria/button.test.tsx` with unit tests covering all variants, sizes, disabled state, focus ring, and keyboard activation in `frontend/app/src/shared/components/aria/button.test.tsx`
- [ ] T026 [US3] Create ButtonWithTooltip and LinkButton composed components in `aria/button.tsx` — ButtonWithTooltip composes Button+Tooltip, LinkButton wraps React Router Link with button styling in `frontend/app/src/shared/components/aria/button.tsx`
- [ ] T027 [US3] Update all 120 consumers of `ui/button` to import from `aria/button` across `frontend/app/src/`
- [ ] T028 [US3] Read `buttons/info-button.tsx`, `buttons/link-toggle-button.tsx`, `buttons/retry.tsx` to determine if they can be inlined at usage sites or should become thin wrappers around aria/button in `frontend/app/src/shared/components/buttons/`
- [ ] T029 [US3] Migrate consumers of `buttons/copy-to-clipboard.tsx` and `buttons/clipboard.tsx` to use `aria/copy-to-clipboard-button.tsx` (already exists) across `frontend/app/src/`
- [ ] T030 [US3] Migrate or inline consumers of `buttons/info-button.tsx`, `buttons/link-toggle-button.tsx`, `buttons/retry.tsx` across `frontend/app/src/`
- [ ] T031 [US3] Delete `ui/button.tsx` and migrated files from `buttons/` directory in `frontend/app/src/shared/components/`
- [ ] T032 [US3] Run `pnpm build && pnpm test && pnpm biome:fix` to verify Button migration in `frontend/app/`

**Checkpoint**: All buttons use the unified aria/button component. Consistent hover, focus, and sizing across the application.

---

## Phase 6: User Story 4 — Unified Checkbox and Toggle Inputs (Priority: P2)

**Goal**: Already completed as part of US1 Phase 3 (PR 4: Checkbox Migration, tasks T012-T014).

**Note**: No additional tasks needed. The inputs/checkbox → aria/checkbox migration was grouped with US1 since it was a low-effort migration (4 consumers) and fit naturally with the selection component consolidation.

---

## Phase 7: User Story 5 — Unified Badge/Tag/Pill Components (Priority: P2)

**Goal**: Create `aria/badge.tsx` with CVA variants absorbing Badge, Pill, and BadgeCircle use cases. Migrate 66 consumers.

**Independent Test**: All status labels, tags, and metadata badges import from `aria/badge`. No imports from `ui/badge`, `display/pill`, or `display/badge-circle` remain.

### Implementation for User Story 5

**PR 6: Badge (66 consumers)**

- [ ] T033 [US5] Read `ui/badge.tsx`, `display/pill.tsx`, and `display/badge-circle.tsx` to catalog all variant systems, props, and consumer patterns in `frontend/app/src/shared/components/`
- [ ] T034 [US5] Create `aria/badge.tsx` with CVA variants covering all Badge (white, gray, dark-gray, green, red, blue, yellow, purple, outline variants), Pill (validate, cancel, warning), and BadgeCircle (with optional onDismiss) use cases in `frontend/app/src/shared/components/aria/badge.tsx`
- [ ] T035 [US5] Create `aria/badge.test.tsx` with unit tests covering all variants, dismiss action, and rendering in `frontend/app/src/shared/components/aria/badge.test.tsx`
- [ ] T036 [US5] Update all 66 consumers of `ui/badge` to import from `aria/badge` across `frontend/app/src/`
- [ ] T037 [US5] Migrate any remaining consumers of `display/pill` and `display/badge-circle` to `aria/badge` across `frontend/app/src/`
- [ ] T038 [US5] Delete `ui/badge.tsx`, `display/pill.tsx`, and `display/badge-circle.tsx` in `frontend/app/src/shared/components/`
- [ ] T039 [US5] Run `pnpm build && pnpm test && pnpm biome:fix` to verify Badge migration in `frontend/app/`

**Checkpoint**: All badges, pills, and status indicators use the unified Badge component with consistent design tokens.

---

## Phase 8: User Story 6 — Unified Accordion/Collapsible Components (Priority: P3)

**Goal**: Create `aria/accordion.tsx` wrapping react-aria Disclosure/DisclosureGroup, replacing both Radix Accordion and custom display/accordion.

**Independent Test**: All collapsible sections import from `aria/accordion`. No imports from `ui/accordion` or `display/accordion` remain.

### Implementation for User Story 6

**PR 9: Accordion (17 consumers)**

- [ ] T040 [US6] Read `display/accordion.tsx` to extract its prop API (title, children, defaultOpen, onToggle) in `frontend/app/src/shared/components/display/accordion.tsx`
- [ ] T041 [US6] Create `aria/accordion.tsx` wrapping react-aria Disclosure and DisclosureGroup with Tailwind styling and expand/collapse animation in `frontend/app/src/shared/components/aria/accordion.tsx`
- [ ] T042 [US6] Create `aria/accordion.test.tsx` with unit tests covering expand/collapse, keyboard interaction, and group behavior in `frontend/app/src/shared/components/aria/accordion.test.tsx`
- [ ] T043 [US6] Update all 16 consumers of `display/accordion` to import from `aria/accordion` across `frontend/app/src/`
- [ ] T044 [US6] Delete `display/accordion.tsx` in `frontend/app/src/shared/components/display/`
- [ ] T045 [US6] Run `pnpm build && pnpm test && pnpm biome:fix` to verify Accordion migration in `frontend/app/`

**Checkpoint**: All collapsible sections use the unified Accordion component with consistent animation and keyboard behavior.

---

## Phase 9: User Story 7 — Unified Modal/Dialog System (Priority: P3)

**Goal**: Refactor SlideOver to compose from aria/modal. Ensure modal-confirm and modal-delete compose from aria/modal.

**Independent Test**: All modal-like overlays (centered dialogs, side panels, confirmation dialogs) share the same react-aria Modal foundation with consistent overlay, close, and focus-trap behavior.

### Implementation for User Story 7

**PR 10: Modal/SlideOver Consolidation**

- [ ] T046 [US7] Read `display/slide-over.tsx`, `modals/modal-confirm.tsx`, and `modals/modal-delete.tsx` to audit which already compose from `aria/modal` in `frontend/app/src/shared/components/`
- [ ] T047 [US7] Refactor `display/slide-over.tsx` to compose from `aria/modal.tsx` (ModalOverlay + Modal) instead of custom overlay implementation in `frontend/app/src/shared/components/display/slide-over.tsx`
- [ ] T048 [US7] If modal-confirm or modal-delete do not compose from aria/modal, refactor them to do so in `frontend/app/src/shared/components/modals/`
- [ ] T049 [US7] Run `pnpm build && pnpm test && pnpm biome:fix` to verify Modal consolidation in `frontend/app/`

**Checkpoint**: All modal-like overlays share the same react-aria Modal foundation.

---

## Phase 10: User Story 8 — Tabs Migration (Priority: P3)

**Goal**: Create `aria/tabs.tsx` wrapping react-aria Tabs, replacing the custom query-param-based tabs implementation.

**Independent Test**: All tab components import from `aria/tabs`. No import of the custom `tabs.tsx` remains. URL query-param synchronization is preserved.

### Implementation for User Story 8

**PR 8: Tabs (21 consumers)**

- [ ] T050 [US8] Read `tabs.tsx` to extract query-param synchronization logic and tab API (Tab, TabList, TabPanel equivalents) in `frontend/app/src/shared/components/tabs.tsx`
- [ ] T051 [US8] Create `aria/tabs.tsx` wrapping react-aria Tabs, TabList, Tab, TabPanel with Tailwind styling and CVA variants in `frontend/app/src/shared/components/aria/tabs.tsx`
- [ ] T052 [US8] Implement URL query-param synchronization as a custom hook (e.g., `useTabsWithSearchParams`) that wraps react-aria Tabs' `onSelectionChange` in `frontend/app/src/shared/components/aria/tabs.tsx`
- [ ] T053 [US8] Create `aria/tabs.test.tsx` with unit tests covering tab selection, keyboard navigation, and query-param sync in `frontend/app/src/shared/components/aria/tabs.test.tsx`
- [ ] T054 [US8] Update all 21 consumers of `tabs` to import from `aria/tabs` across `frontend/app/src/`
- [ ] T055 [US8] Delete `tabs.tsx` in `frontend/app/src/shared/components/`
- [ ] T056 [US8] Run `pnpm build && pnpm test && pnpm biome:fix` to verify Tabs migration in `frontend/app/`

**Checkpoint**: All tabs use the unified react-aria Tabs component with consistent keyboard navigation and preserved URL sync.

---

## Phase 11: Dependency Removal and Cleanup (Priority: P3)

**Goal**: Remove all Radix, Headless UI, and cmdk packages that are no longer imported. Verify bundle size decrease.

**Independent Test**: `pnpm build` succeeds with packages removed. No Radix/Headless UI/cmdk code in the production bundle.

### Implementation

- [ ] T057 [US9] Grep entire `frontend/app/src/` for any remaining imports from `@radix-ui/react-dropdown-menu`, `@radix-ui/react-popover`, `@radix-ui/react-tooltip`, `@radix-ui/react-accordion`, `@radix-ui/react-tabs`, `@radix-ui/react-label`, `@headlessui/react`, and `cmdk` — fix any remaining references
- [ ] T058 [US9] Remove the following from `frontend/app/package.json`: `@radix-ui/react-dropdown-menu`, `@radix-ui/react-popover`, `@radix-ui/react-tooltip`, `@radix-ui/react-accordion`, `@radix-ui/react-tabs`, `@radix-ui/react-label`, `@headlessui/react`, `cmdk`
- [ ] T059 [US9] Verify packages that MUST remain: `@radix-ui/react-scroll-area`, `@radix-ui/react-progress`, `@radix-ui/react-slot` — confirm they have no removed-package transitive imports in `frontend/app/package.json`
- [ ] T060 [US9] Run `pnpm install && pnpm build && pnpm test && pnpm biome:fix` to verify full build with reduced dependencies in `frontend/app/`
- [ ] T061 [US9] Add Towncrier changelog fragment documenting the component library consolidation and dependency removal in `changelog/`

**Checkpoint**: All legacy UI library packages removed. Bundle size verified to be equal or smaller.

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Final verification across all migrated components

- [ ] T062 [P] Verify no dead imports — grep for any remaining references to deleted files (`ui/button`, `ui/badge`, `ui/tooltip`, `ui/popover`, `ui/dropdown-menu`, `ui/combobox`, `ui/command`, `ui/accordion`, `display/accordion`, `display/pill`, `display/badge-circle`, `inputs/checkbox`, `buttons/copy-to-clipboard`, `buttons/clipboard`, `buttons/info-button`, `buttons/link-toggle-button`, `buttons/retry`) across `frontend/app/src/`
- [ ] T063 [P] Run full E2E test suite (`pnpm test:e2e`) to verify no user-facing regressions in `frontend/app/`
- [ ] T064 Verify visual consistency — spot-check tooltips, popovers, buttons, badges, and menus across 5+ screens to confirm consistent design tokens in the running application

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: N/A — no blocking prerequisites exist
- **User Stories (Phases 3-11)**: Can begin after Setup
  - US1 (Phase 3) and US2 (Phase 4) are independent and can run in parallel
  - US3 (Phase 5) depends on US2 (Tooltip) because ButtonWithTooltip imports Tooltip
  - US4 (Phase 6) completed within US1
  - US5 (Phase 7) is independent
  - US6 (Phase 8) is independent
  - US7 (Phase 9) is independent
  - US8 (Phase 10) is independent
  - US9 (Phase 11) MUST be last — depends on ALL other stories completing
- **Polish (Phase 12)**: Depends on all user stories completing

### User Story Dependencies

- **US1 (Selection/Action)**: Independent — can start immediately
- **US2 (Tooltip/Popover)**: Independent — can start immediately
- **US3 (Button)**: Depends on US2 (ButtonWithTooltip uses aria/tooltip)
- **US4 (Checkbox)**: Completed within US1
- **US5 (Badge)**: Independent — can start after Setup
- **US6 (Accordion)**: Independent — can start after Setup
- **US7 (Modal/SlideOver)**: Independent — can start after Setup
- **US8 (Tabs)**: Independent — can start after Setup
- **US9 (Dependency Removal)**: Depends on ALL previous stories

### Within Each User Story

1. Read existing component APIs (understand before changing)
2. Create new aria/ component (if needed) with unit tests
3. Update all consumers (hard cut — all in same PR)
4. Delete old component files
5. Build + test verification

### Parallel Opportunities

- **US1 + US2**: Can run in parallel (different component categories, different files)
- **US5 + US6 + US7 + US8**: Can all run in parallel after US2 completes (for US3 dependency)
- Within US1: Menu (T003-T006) and Checkbox (T012-T014) PRs can run in parallel
- Within US2: Tooltip (T015-T018) and Popover (T019-T022) PRs can run in parallel

---

## Parallel Example: User Stories 1 + 2

```bash
# These two story groups can run in parallel:

# Stream 1: US1 — Selection/Action Components
Task: "Map Radix DropdownMenu API to react-aria Menu API"
Task: "Update 8 Menu consumers"
Task: "Map cmdk API to react-aria Autocomplete API"
Task: "Update 35 Combobox consumers"
Task: "Update 4 Checkbox consumers"

# Stream 2: US2 — Tooltip/Popover
Task: "Map Radix Tooltip API to react-aria Tooltip API"
Task: "Update 41 Tooltip consumers"
Task: "Map Radix Popover API to react-aria Popover API"
Task: "Update 29 Popover consumers"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 3: US1 — Selection/Action (T003-T014)
3. Complete Phase 4: US2 — Tooltip/Popover (T015-T022)
4. **STOP and VALIDATE**: All low-risk migrations done. ~82 consumer files updated. Radix DropdownMenu, cmdk, native checkbox, Radix Tooltip, and Radix Popover eliminated.

### Incremental Delivery

1. US1 + US2 → Low-risk foundation (no new components created)
2. US3 (Button) → Highest-impact new component (120 consumers)
3. US5 (Badge) → Second-highest impact (66 consumers)
4. US1-cmdk (Autocomplete) → Remove cmdk dependency (35 consumers)
5. US8 (Tabs) → Medium effort (21 consumers)
6. US6 (Accordion) + US7 (Modal) → Low effort remaining work
7. US9 (Cleanup) → Remove packages, verify bundle

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Hard-cut strategy: old component deleted in same PR as consumer migration
- Form field wrappers (`form/fields/*.field.tsx`) are explicitly OUT OF SCOPE
- Components with no react-aria equivalent (card, alert, spinner, pagination, scroll-area, resizable, form, link, kbd) remain in `ui/`
