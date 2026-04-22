# Implementation Plan: Unify UI Components

**Branch**: `infp-561-unify-ui-components` | **Date**: 2026-04-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/infp-561-unify-ui-components/spec.md`

## Summary

Consolidate ~45 duplicated UI components (scattered across `ui/`, `aria/`, `inputs/`, `display/`, `buttons/`, `modals/`) into a single unified `shared/components/aria/` directory backed by react-aria-components. The migration replaces Radix UI, Headless UI, and cmdk dependencies with react-aria equivalents, following a hard-cut-per-component strategy where each PR migrates a component and all its consumers simultaneously.

## Technical Context

**Language/Version**: TypeScript 5.9, React 19.2
**Primary Dependencies**: react-aria-components 1.17.0, class-variance-authority 0.7.1, Tailwind CSS 4.2
**Storage**: N/A (frontend-only, no data layer changes)
**Testing**: Vitest (unit/component), Playwright (E2E)
**Target Platform**: Web (modern browsers)
**Project Type**: Web application — frontend only
**Performance Goals**: Bundle size must not increase (target: net decrease from removing Radix + Headless UI + cmdk)
**Constraints**: React Compiler enabled (no memo/useMemo/useCallback), pure components required, no `any` types
**Scale/Scope**: ~350 consumer files to update across 10 PRs, 4 new components to create, ~18 old components to delete

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | N/A | No schema/data changes |
| II. Branch-Safe by Default | N/A | Frontend-only, no branch model interaction |
| III. Type Safety & Explicit Contracts | PASS | All components use TypeScript with proper props interfaces. No `any`. Named exports. |
| IV. Test Discipline | PASS | Each migrated component gets colocated unit tests. E2E tests updated for import paths. |
| V. Query Performance | N/A | No database queries |
| VI. Security & Input Boundaries | N/A | No user input handling changes |
| VII. Simplicity & Maintainability | PASS | Migration reduces complexity: fewer components, single library, single directory. CVA used only where variants justify it (>= 2 visual variants). |

**Quality Gates**:
- Formatting: `pnpm biome:fix` — enforced per PR
- Linting: Biome — zero errors per PR
- Type checking: TypeScript strict — no `type: ignore` additions
- Tests: All existing tests pass + new unit tests for created components
- Changelog: Towncrier fragment per PR

**Gate Result**: PASS — no violations.

## Project Structure

### Documentation (this feature)

```text
specs/infp-561-unify-ui-components/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0: decisions and rationale
├── data-model.md        # Phase 1: component API contracts
├── quickstart.md        # Phase 1: migration workflow guide
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
frontend/app/src/shared/components/
├── aria/                          # TARGET: unified component directory
│   ├── button.tsx                 # NEW: react-aria Button + CVA
│   ├── badge.tsx                  # NEW: unified Badge (replaces ui/badge + display/pill + display/badge-circle)
│   ├── tabs.tsx                   # NEW: react-aria Tabs (replaces custom tabs.tsx)
│   ├── accordion.tsx              # NEW: react-aria Disclosure (replaces ui/accordion + display/accordion)
│   ├── select.tsx                 # EXISTING: unchanged
│   ├── menu.tsx                   # EXISTING: unchanged (absorbs Radix dropdown-menu consumers)
│   ├── list-box.tsx               # EXISTING: unchanged
│   ├── autocomplete.tsx           # EXISTING: absorbs cmdk/combobox consumers
│   ├── tooltip.tsx                # EXISTING: absorbs Radix tooltip consumers
│   ├── popover.tsx                # EXISTING: absorbs Radix popover consumers
│   ├── modal.tsx                  # EXISTING: SlideOver composed from this
│   ├── checkbox.tsx               # EXISTING: absorbs inputs/checkbox consumers
│   ├── radio-group.tsx            # EXISTING: unchanged
│   ├── breadcrumbs.tsx            # EXISTING: unchanged
│   ├── label.tsx                  # EXISTING: unchanged
│   ├── separator.tsx              # EXISTING: unchanged
│   ├── tree.tsx                   # EXISTING: unchanged
│   ├── copy-to-clipboard-button.tsx # EXISTING: unchanged
│   ├── style-rac.ts              # EXISTING: shared style tokens
│   └── utils/
│       └── stacked.tsx            # EXISTING: modal stacking utility
│
├── ui/                            # TO DELETE (after migration)
│   ├── button.tsx                 # → aria/button.tsx
│   ├── badge.tsx                  # → aria/badge.tsx
│   ├── tooltip.tsx                # → aria/tooltip.tsx
│   ├── popover.tsx                # → aria/popover.tsx
│   ├── dropdown-menu.tsx          # → aria/menu.tsx
│   ├── combobox.tsx               # → aria/autocomplete.tsx
│   ├── command.tsx                # → aria/autocomplete.tsx (cmdk removed)
│   ├── accordion.tsx              # → aria/accordion.tsx
│   ├── card.tsx                   # KEEP (no react-aria equivalent needed)
│   ├── alert.tsx                  # KEEP (no react-aria equivalent needed)
│   ├── spinner.tsx                # KEEP (no react-aria equivalent needed)
│   ├── pagination.tsx             # KEEP (uses react-paginate, out of scope)
│   ├── input.tsx                  # KEEP (form field wrapper scope is deferred)
│   ├── password-input.tsx         # KEEP (form field wrapper scope is deferred)
│   ├── scroll-area.tsx            # KEEP (Radix ScrollArea, no react-aria equivalent)
│   ├── resizable.tsx              # KEEP (no react-aria equivalent)
│   ├── form.tsx                   # KEEP (react-hook-form integration)
│   ├── link.tsx                   # KEEP (React Router, not a react-aria concern)
│   └── kbd.tsx                    # KEEP (simple display component)
│
├── display/
│   ├── accordion.tsx              # → aria/accordion.tsx
│   ├── pill.tsx                   # → aria/badge.tsx
│   ├── badge-circle.tsx           # → aria/badge.tsx
│   └── slide-over.tsx             # → compose from aria/modal.tsx
│
├── buttons/
│   ├── copy-to-clipboard.tsx      # → aria/copy-to-clipboard-button.tsx (already exists)
│   ├── clipboard.tsx              # → aria/copy-to-clipboard-button.tsx (already exists)
│   ├── info-button.tsx            # → compose from aria/button.tsx
│   ├── link-toggle-button.tsx     # → compose from aria/button.tsx
│   └── retry.tsx                  # → compose from aria/button.tsx
│
├── inputs/
│   └── checkbox.tsx               # → aria/checkbox.tsx (already exists)
│
├── modals/
│   ├── modal-confirm.tsx          # → compose from aria/modal.tsx
│   └── modal-delete.tsx           # → compose from aria/modal.tsx
│
└── tabs.tsx                       # → aria/tabs.tsx
```

**Structure Decision**: The `aria/` directory is the consolidation target. Components that have no react-aria equivalent (card, alert, spinner, pagination, scroll-area, resizable, form, link, kbd) remain in `ui/`. The `ui/` directory is NOT fully deleted — only the components that have react-aria replacements are removed.

## Implementation Phases

### Phase 1: Low-Risk Migrations (existing aria/ components absorb Radix consumers)

These PRs replace Radix components where an aria/ equivalent already exists. No new components are created — only consumer imports are updated and old files deleted.

**PR 1: Tooltip Migration** (41 consumers)
- Update all 41 files importing from `ui/tooltip` to import from `aria/tooltip`
- Adapt any prop/API differences (Radix TooltipProvider → react-aria TooltipTrigger)
- Delete `ui/tooltip.tsx`
- Colocated test: `aria/tooltip.test.tsx` (if not present)

**PR 2: Popover Migration** (29 consumers)
- Update all 29 files importing from `ui/popover` to import from `aria/popover`
- Handle PopoverTabs migration (ui/popover exports PopoverTabs which may need a separate approach)
- Delete `ui/popover.tsx`
- Colocated test: `aria/popover.test.tsx` (if not present)

**PR 3: Menu Migration** (8 consumers)
- Update all 8 files importing from `ui/dropdown-menu` to import from `aria/menu`
- Map Radix DropdownMenu API to react-aria Menu API
- Delete `ui/dropdown-menu.tsx`
- Delete `ui/accordion.tsx` (only consumer was dropdown-menu)

**PR 4: Checkbox Migration** (4 consumers)
- Update all 4 files importing from `inputs/checkbox` to import from `aria/checkbox`
- Delete `inputs/checkbox.tsx`

### Phase 2: New Components + Large Migrations

These PRs create new aria/ components and handle the high-consumer-count migrations.

**PR 5: Button** (120 consumers) — LARGEST PR
- Create `aria/button.tsx` wrapping react-aria Button with CVA variants matching current ui/button API
- Create `aria/button.test.tsx`
- Update all 120 consumer files
- Migrate specialized buttons:
  - `buttons/info-button.tsx` → inline compose or keep as thin wrapper around aria/button
  - `buttons/link-toggle-button.tsx` → react-aria ToggleButton or compose
  - `buttons/retry.tsx` → compose from aria/button
  - `buttons/copy-to-clipboard.tsx` and `buttons/clipboard.tsx` → aria/copy-to-clipboard-button.tsx (already exists)
- Delete `ui/button.tsx` and migrated `buttons/*.tsx` files

**PR 6: Badge** (66 consumers)
- Create `aria/badge.tsx` with CVA variants covering all current Badge + Pill + BadgeCircle use cases
- Create `aria/badge.test.tsx`
- Update all 66 consumer files importing from `ui/badge`
- Migrate Pill consumers (verify if any exist — audit showed ~0)
- Migrate BadgeCircle consumers (verify if any exist — audit showed ~0)
- Delete `ui/badge.tsx`, `display/pill.tsx`, `display/badge-circle.tsx`

**PR 7: Combobox/cmdk → Autocomplete** (35 consumers)
- Update all 35 files importing from `ui/combobox` to use `aria/autocomplete`
- Map cmdk Command API to react-aria Autocomplete API
- Delete `ui/combobox.tsx` and `ui/command.tsx`
- Remove `cmdk` from package.json dependencies

### Phase 3: Remaining Components

**PR 8: Tabs** (21 consumers)
- Create `aria/tabs.tsx` wrapping react-aria Tabs
- Handle query-param synchronization (current tabs.tsx integrates with URL search params)
- Create `aria/tabs.test.tsx`
- Update all 21 consumer files
- Delete `tabs.tsx`

**PR 9: Accordion** (17 consumers total)
- Create `aria/accordion.tsx` wrapping react-aria Disclosure/DisclosureGroup
- Create `aria/accordion.test.tsx`
- Update 16 consumers of `display/accordion` and 1 consumer of `ui/accordion`
- Delete `display/accordion.tsx` and `ui/accordion.tsx`

**PR 10: Modal/SlideOver Consolidation**
- Refactor `display/slide-over.tsx` to compose from `aria/modal.tsx`
- Ensure `modals/modal-confirm.tsx` and `modals/modal-delete.tsx` compose from `aria/modal.tsx` (may already do so)
- Move surviving SlideOver into `aria/` or keep as composed component in `display/`

### Phase 4: Cleanup

**PR 11: Dependency Removal**
- Remove from package.json:
  - `@radix-ui/react-dropdown-menu`
  - `@radix-ui/react-popover`
  - `@radix-ui/react-tooltip`
  - `@radix-ui/react-tabs` (if used by custom tabs — verify)
  - `@radix-ui/react-accordion`
  - `@radix-ui/react-label` (if no longer used)
  - `@headlessui/react`
  - `cmdk`
- Keep Radix packages still in use: `@radix-ui/react-scroll-area`, `@radix-ui/react-progress`, `@radix-ui/react-slot`
- Run full build + test suite to verify
- Changelog fragment for bundle size reduction

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Button PR (120 files) is too large for review | HIGH | Split by consumer domain: forms, tables, navigation, actions |
| react-aria API differences break existing behavior | MEDIUM | Write unit tests for each new component BEFORE consumer migration |
| cmdk → Autocomplete loses fuzzy search behavior | MEDIUM | Verify react-aria Autocomplete supports same filtering; add custom filter if needed |
| Tabs query-param integration lost | MEDIUM | Implement URL sync as a custom hook wrapping react-aria Tabs |
| Removed Radix packages still imported transitively | LOW | Tree-shake check + build verification |
| E2E tests break due to changed DOM structure | MEDIUM | react-aria renders different ARIA attributes; update test selectors |

## Complexity Tracking

No constitution violations to justify. The migration reduces complexity:
- ~45 component files → ~25 unified components (44% reduction)
- 3 UI libraries → 1 (react-aria-components)
- 6 component directories → 1 primary (`aria/`) + `ui/` for non-react-aria components
