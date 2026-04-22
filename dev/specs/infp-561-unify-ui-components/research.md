# Research: Unify UI Components

**Branch**: `infp-561-unify-ui-components` | **Date**: 2026-04-22

## Decision 1: Component Taxonomy

**Decision**: Select, ListBox, Menu, and Autocomplete are four distinct react-aria primitives with non-overlapping purposes. They are NOT interchangeable "dropdown" variants.

**Rationale**:
- **Select**: Form control for picking a single value (replaces HTML `<select>`)
- **ListBox**: Standalone selectable list for inline/embedded selection
- **Menu**: Action trigger (edit, delete, navigate) — not for data selection
- **Autocomplete**: Searchable type-ahead with client/server filtering

**Alternatives considered**: Treating all as a single "Dropdown" category. Rejected because it conflates form value selection with action triggering, leading to incorrect component usage.

## Decision 2: cmdk Replacement

**Decision**: Migrate all cmdk/Combobox usages to react-aria Autocomplete. Remove cmdk dependency.

**Rationale**: The codebase already has `aria/autocomplete.tsx` (react-aria Autocomplete) which supports both client and server-side filtering. cmdk serves the same purpose but uses a different library, creating duplication. Unlike react-datepicker (no react-aria equivalent), Autocomplete is a direct replacement.

**Alternatives considered**:
- Keep cmdk for command-palette-style interactions only → rejected: not enough differentiation to justify two libraries
- Keep cmdk out of scope entirely → rejected: direct react-aria equivalent exists

## Decision 3: Unified Directory

**Decision**: Consolidate all migrated components into the existing `shared/components/aria/` directory.

**Rationale**: The `aria/` directory already contains 16 react-aria component files with established patterns (composeRenderProps, classNames, named exports). Moving Radix components here avoids a disruptive rename while establishing a single source of truth.

**Alternatives considered**:
- New `shared/components/primitives/` directory → rejected: unnecessary rename of 16 existing files
- Keep current directory structure, replace in-place → rejected: developers still need to know which directory to look in

## Decision 4: Migration Strategy

**Decision**: Hard cut per component. When a component is migrated, all its consumers are updated in the same PR.

**Rationale**: Avoids a long coexistence period with re-exports and deprecated import warnings. Each PR is self-contained and testable — the old component file is deleted, not left as a re-export wrapper.

**Alternatives considered**:
- Re-export from old paths + lint rule → rejected: creates dead code that lingers
- Lazy consumer updates → rejected: leaves broken or inconsistent imports

## Decision 5: Form Field Wrappers Scope

**Decision**: Form field wrappers (`form/fields/*.field.tsx`) are out of scope. They will be updated in a follow-up effort.

**Rationale**: Form field wrappers are thin react-hook-form integrations around base components. Updating them alongside the base components would significantly expand PR scope without proportional benefit. They can be updated incrementally once the base components stabilize.

## Decision 6: No aria/button.tsx Exists Yet

**Decision**: Create a new `aria/button.tsx` wrapping react-aria-components Button with CVA variants, as the first new aria component.

**Rationale**: The current `ui/button.tsx` has 120 consumers — the largest migration target. It already uses CVA variants (primary, outline, danger, ghost, etc.) which should be preserved. react-aria Button provides built-in keyboard activation, focus management, and disabled state handling.

**Alternatives considered**: Keep ui/button.tsx as-is since it works → rejected: inconsistent with the goal of consolidating everything into aria/

## Decision 7: Existing aria/ Component Patterns

**Decision**: Follow the established patterns in existing aria/ components for all new/migrated components.

**Rationale**: The 16 existing aria components have consistent patterns:
- Wrap react-aria-components primitives with Tailwind styling
- Use `composeRenderProps()` for dynamic state styling
- Use shared style tokens from `style-rac.ts` (disabledStyle, focusVisibleStyle)
- Named exports, kebab-case files, no barrel exports
- CVA used selectively (tooltip, breadcrumbs, label)

These patterns should be extended to all new components, with CVA adoption expanded for components with multiple visual variants (Button, Badge).

## Consumer Impact Analysis

Migration effort ordered by consumer count:

| Component | Consumers | Effort |
|-----------|-----------|--------|
| ui/button | 120 files | HIGH — largest PR, most testing needed |
| aria/* (already migrated) | 86 files | NONE — already using react-aria |
| ui/badge | 66 files | HIGH — many consumers across schema, diff, branches |
| ui/tooltip | 41 files | MEDIUM — straightforward 1:1 replacement |
| ui/combobox (cmdk) | 35 files | MEDIUM — API change from cmdk to react-aria Autocomplete |
| ui/popover | 29 files | MEDIUM — straightforward 1:1 replacement |
| ui/tabs | 21 files | MEDIUM — custom query-param tabs to react-aria Tabs |
| display/accordion | 16 files | LOW — two implementations to one |
| buttons/* | 11 files | LOW — compose from new aria/button |
| ui/dropdown-menu | 8 files | LOW — Radix to react-aria Menu |
| inputs/checkbox | 4 files | LOW — HTML to react-aria Checkbox |
| ui/accordion | 1 file | LOW — only used in dropdown-menu |
| display/pill | ~0 files | LOW — possibly unused, verify before migrating |
| display/badge-circle | ~0 files | LOW — possibly unused, verify before migrating |
