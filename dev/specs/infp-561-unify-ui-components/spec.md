# Feature Specification: Unify UI Components with react-aria-components

**Feature Branch**: `infp-561-unify-ui-components`  
**Created**: 2026-04-22  
**Status**: Draft  
**Input**: Consolidate duplicated UI components into a unified react-aria-components design system

## Clarifications

### Session 2026-04-22

- Q: Select, ListBox, and Menu are distinct component types with different purposes — should the spec treat them as separate categories? → A: Yes. Select (form value selection), ListBox (standalone selectable list), and Menu (action triggering) are distinct primitives, not duplicates of each other. Duplication exists only within each type (Radix vs react-aria).
- Q: Should cmdk/Combobox be migrated to react-aria Autocomplete or kept as a third-party dependency? → A: Migrate all cmdk/Combobox usages to react-aria Autocomplete; remove cmdk dependency.
- Q: Where should unified components live after migration? → A: Consolidate into the existing `aria/` directory. Already-migrated components keep their paths; Radix/custom components move into `aria/`. Empty directories (`ui/`, etc.) are removed.
- Q: Should form field wrappers (`form/fields/*.field.tsx`) be updated as part of this migration? → A: Out of scope. Form field wrappers will be updated in a separate follow-up effort.
- Q: How should old component imports be handled during the transition? → A: Hard cut per component. When a component is migrated to `aria/`, all its consumers are updated in the same PR. No re-exports or lazy migration.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consolidate Selection and Action Components (Priority: P1)

A developer uses four distinct react-aria primitives — each serving a different purpose — instead of choosing between overlapping Radix, cmdk, and custom implementations:

- **Select**: Form control for picking a single value from a predefined list (replaces Radix Combobox used as select, custom Enum input)
- **Autocomplete**: Searchable type-ahead input with filtering for large or dynamic datasets (replaces cmdk-based Combobox, cmdk Command)
- **ListBox**: Standalone selectable list for inline selection, multi-select, or embedded item lists (already react-aria, no Radix duplicate)
- **Menu**: Action trigger for contextual actions like edit, delete, navigate (replaces Radix DropdownMenu)

**Why this priority**: These four component types account for the highest duplication (8+ implementations across 3 libraries). Consolidating within each type eliminates the largest source of inconsistency while preserving their distinct semantic roles.

**Independent Test**: A developer can build a form with a static select, a searchable autocomplete, an inline list, and a contextual action menu using the four distinct react-aria primitives, each with clear and non-overlapping purpose.

**Acceptance Scenarios**:

1. **Given** a developer needs a form field for choosing from a fixed set of values, **When** they import from the unified component library, **Then** they find the Select component (not a searchable combobox or menu)
2. **Given** a developer needs a searchable type-ahead input, **When** they import from the unified component library, **Then** they find the Autocomplete component (replacing all cmdk-based implementations)
3. **Given** a developer needs a contextual action menu (edit, delete, etc.), **When** they import from the unified component library, **Then** they find the Menu component (not a select or listbox)
4. **Given** a developer needs an inline selectable list (e.g., relationship items, multi-select), **When** they import from the unified component library, **Then** they find the ListBox component
5. **Given** any of these four components is open/focused, **When** the user navigates with keyboard (arrow keys, type-ahead, Escape), **Then** keyboard behavior follows react-aria conventions consistently

---

### User Story 2 - Consistent Tooltip/Popover Overlays (Priority: P1)

A developer adding contextual information or floating content uses a single tooltip and a single popover component instead of choosing between Radix Tooltip/Popover and React Aria Tooltip/Popover (which have different APIs, colors, and portal behavior).

**Why this priority**: Tooltips and popovers appear throughout the app. Having two parallel implementations with different visual designs (gray-600 vs neutral-700 backgrounds) creates visible inconsistency for end users.

**Independent Test**: Replace all Radix tooltip/popover usages with react-aria equivalents and verify consistent styling, positioning, and keyboard accessibility across the app.

**Acceptance Scenarios**:

1. **Given** a component needs a tooltip, **When** the developer imports Tooltip, **Then** there is exactly one Tooltip component from the unified library
2. **Given** a component needs floating content with interaction (forms, menus), **When** the developer imports Popover, **Then** there is exactly one Popover component from the unified library
3. **Given** tooltips appear on different screens, **When** the user views them, **Then** they all share the same visual design (background color, border radius, font size, arrow style)

---

### User Story 3 - Unified Button System (Priority: P2)

A developer building any interactive element uses the base Button component with variant props, instead of creating specialized button components that duplicate styling logic (copy-to-clipboard, info button, link toggle, retry button, data viewer buttons).

**Why this priority**: Buttons are the most common interactive element. Five separate implementations mean inconsistent hover states, focus rings, sizes, and spacing. Unifying them under react-aria Button ensures consistent accessibility (focus management, keyboard activation).

**Independent Test**: All existing button use cases (primary, outline, icon-only, link-style, with tooltip) can be expressed using the unified Button component and its variant system.

**Acceptance Scenarios**:

1. **Given** a developer needs an icon-only button, **When** they use the unified Button with an icon variant, **Then** it renders with correct accessible label and consistent sizing
2. **Given** a developer needs a button that copies text to clipboard, **When** they compose the unified Button with a copy behavior hook, **Then** the button styling matches all other buttons
3. **Given** a developer needs a link-styled button, **When** they use the unified Button with a link variant or the LinkButton subcomponent, **Then** focus and hover states are consistent with all other buttons

---

### User Story 4 - Unified Checkbox and Toggle Inputs (Priority: P2)

A developer building a form uses a single Checkbox component (react-aria) instead of choosing between the native HTML checkbox wrapper and the React Aria checkbox, which have different APIs, styles, and accessibility behavior.

**Why this priority**: Two checkbox implementations with different visual treatments create inconsistency in forms. React Aria provides superior accessibility (indeterminate state, group management, labeling).

**Independent Test**: All form checkboxes across the app use the unified react-aria Checkbox component with consistent visual design and keyboard behavior.

**Acceptance Scenarios**:

1. **Given** a form has a boolean field, **When** the developer adds a checkbox, **Then** they use the single react-aria Checkbox component
2. **Given** a group of related checkboxes, **When** the developer creates a checkbox group, **Then** they use react-aria CheckboxGroup with consistent styling and accessible group labeling
3. **Given** a user tabs through a form, **When** they reach a checkbox, **Then** focus ring style matches all other form inputs

---

### User Story 5 - Unified Badge/Tag/Pill Components (Priority: P2)

A developer displaying status labels, tags, or metadata uses a single Badge component with variant props instead of choosing between Badge, Pill, and BadgeCircle (three incompatible components with different variant systems).

**Why this priority**: Three label-like components with different APIs (CVA-based Badge, enum-based Pill, enum-based BadgeCircle) force developers to pick between them and create visual inconsistency.

**Independent Test**: All current Badge, Pill, and BadgeCircle use cases are expressible through a single Badge component with appropriate variant props.

**Acceptance Scenarios**:

1. **Given** a developer needs a status indicator (validate, cancel, warning), **When** they use the unified Badge component, **Then** they select a semantic variant (success, danger, warning) that maps to the correct color scheme
2. **Given** a developer needs a removable tag, **When** they use the unified Badge with a dismiss action, **Then** the dismiss button is accessible and consistently styled
3. **Given** badges appear in tables, forms, and detail views, **When** the user views them, **Then** colors, sizing, and typography are consistent across all contexts

---

### User Story 6 - Unified Accordion/Collapsible Components (Priority: P3)

A developer adding expandable content sections uses a single Accordion component (react-aria Disclosure/DisclosureGroup) instead of choosing between Radix Accordion and the custom display/accordion (two separate implementations with different APIs).

**Why this priority**: Lower usage frequency than dropdowns or buttons, but the two implementations have incompatible prop APIs, causing developer friction.

**Independent Test**: All expandable/collapsible sections across the app use the unified react-aria Disclosure component with consistent animation and keyboard behavior.

**Acceptance Scenarios**:

1. **Given** a page has collapsible sections, **When** the developer implements them, **Then** they use a single Accordion component from the unified library
2. **Given** a user presses Enter or Space on a collapsed section header, **When** the section expands, **Then** animation and focus behavior is consistent regardless of where the accordion appears

---

### User Story 7 - Unified Modal/Dialog System (Priority: P3)

A developer adding overlay dialogs uses a unified Modal/Dialog system where confirmation dialogs, delete dialogs, and slide-over panels share a common foundation, with the react-aria Modal as the single base.

**Why this priority**: Modals are already partially migrated to react-aria. The remaining work is to bring SlideOver and specialized variants (confirm, delete) into a consistent compositional pattern.

**Independent Test**: All modal-like overlays (centered dialogs, confirmation dialogs, side panels) use the react-aria Modal as their base, with consistent overlay dimming, close behavior, and focus trapping.

**Acceptance Scenarios**:

1. **Given** a developer needs a side panel, **When** they use the SlideOver component, **Then** it composes the same react-aria Modal/ModalOverlay primitives as centered dialogs
2. **Given** a user opens a confirmation dialog, **When** they press Escape, **Then** the dialog closes with the same behavior as all other modals
3. **Given** multiple modals are stacked, **When** the user dismisses the top one, **Then** focus returns to the previous modal correctly

---

### User Story 8 - Removal of Radix and Headless UI Dependencies (Priority: P3)

After all components are migrated to react-aria-components, the legacy Radix UI packages (`@radix-ui/react-accordion`, `@radix-ui/react-dropdown-menu`, `@radix-ui/react-popover`, `@radix-ui/react-tabs`, `@radix-ui/react-tooltip`, `@radix-ui/react-label`, `@radix-ui/react-progress`, `@radix-ui/react-scroll-area`) and `@headlessui/react` are removed from dependencies.

**Why this priority**: Dependency cleanup is a final step after migration. Reducing bundle size and eliminating conflicting accessibility implementations.

**Independent Test**: The application builds and passes all tests with Radix UI and Headless UI packages removed from package.json.

**Acceptance Scenarios**:

1. **Given** all components are migrated, **When** Radix/Headless UI packages are removed from package.json, **Then** the app builds without errors
2. **Given** the app is built, **When** the bundle is analyzed, **Then** no Radix or Headless UI code is included
3. **Given** all Radix/Headless UI imports are removed, **When** the linter runs, **Then** no unused import warnings remain

---

### Edge Cases

- What happens when a component is used in a deeply nested context (e.g., a select inside a modal inside a slide-over)? Focus trapping and z-index stacking must work correctly.
- How does the system handle components that are mid-migration (some screens use old, some use new)? Both old and new must coexist during the transition period without visual conflicts.
- What happens when a third-party library (react-datepicker, cmdk, react-paginate) conflicts with react-aria's focus management? Integration boundaries must be clearly defined.
- How does the system handle right-to-left (RTL) layouts? react-aria-components has built-in RTL support that the custom implementations may lack.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The unified component library MUST provide four distinct selection/action primitives based on react-aria-components — Select (form value selection), Autocomplete (searchable type-ahead), ListBox (standalone selectable list), and Menu (action triggering) — each with a clear, non-overlapping purpose, replacing all Radix, cmdk, and custom implementations within each category
- **FR-002**: The unified component library MUST provide a single Tooltip and Popover component based on react-aria-components, replacing Radix Tooltip and Popover
- **FR-003**: The unified Button component MUST support all current variant needs (primary, outline, danger, ghost, icon-only, link-style) through a single component with variant props
- **FR-004**: The unified Checkbox component MUST replace both the native HTML checkbox wrapper and the existing react-aria checkbox with a single implementation
- **FR-005**: The unified Badge component MUST cover all current Badge, Pill, and BadgeCircle use cases through variant props
- **FR-006**: The unified Accordion component MUST replace both Radix Accordion and custom display/accordion with a single react-aria Disclosure-based implementation
- **FR-007**: The unified Modal MUST serve as the foundation for centered dialogs, confirmation dialogs, delete dialogs, and slide-over panels
- **FR-008**: All unified components MUST use Tailwind CSS with CVA (class-variance-authority) for variant management, matching the existing styling approach
- **FR-009**: All unified components MUST meet WCAG 2.1 AA accessibility standards (keyboard navigation, screen reader support, focus management, ARIA attributes)
- **FR-010**: The migration MUST be incremental per component category — when a component is migrated, all its consumers MUST be updated in the same PR (hard cut, no re-exports or coexistence period per component)
- **FR-011**: After full migration, all Radix UI packages and @headlessui/react MUST be removable from package.json without build errors
- **FR-012**: All unified components MUST preserve existing functionality — no user-facing feature regressions during migration
- **FR-013**: The unified component library MUST provide a Tabs component based on react-aria-components, replacing the custom query-param-based implementation

### Key Entities

- **Component Primitive**: A single-purpose, accessible UI building block (Button, Select, Tooltip, etc.) backed by react-aria-components
- **Variant**: A visual/behavioral configuration of a primitive (e.g., Button with variant "danger", Badge with variant "success")
- **Composition Pattern**: How primitives combine to form complex components (e.g., Modal + Form = confirmation dialog, Button + Tooltip = ButtonWithTooltip)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The number of UI primitive component files is reduced by at least 40% (from current ~45 component files across ui/, aria/, inputs/, display/ to ~25 unified components)
- **SC-002**: Developers can build any form, menu, or overlay using components from the `aria/` directory as the single unified source, without needing to choose between competing implementations in `ui/`, `inputs/`, or `display/`
- **SC-003**: All interactive components pass automated accessibility audits (axe-core) with zero critical or serious violations
- **SC-004**: Visual consistency is achieved: every tooltip, popover, dropdown, button, and badge across the application shares the same design tokens (colors, spacing, border-radius, typography)
- **SC-005**: The production bundle size does not increase after migration (target: net decrease due to removing Radix + Headless UI dependencies)
- **SC-006**: 100% of existing E2E tests pass after migration with no modifications to test assertions (only import path changes allowed)
- **SC-007**: New developers can identify and use the correct component for any use case within 2 minutes by consulting a single component directory

## Assumptions

- react-aria-components (already at v1.17.0 in the project) will remain the target library — no further library evaluation needed
- The existing react-aria components in `src/shared/components/aria/` (modal, select, menu, list-box, tooltip, popover, checkbox, breadcrumbs, etc.) are the starting foundation and their APIs are acceptable
- CVA (class-variance-authority) remains the variant management approach
- Tailwind CSS 4.x remains the styling framework
- Third-party specialized components (react-datepicker, react-paginate, @uiw/react-color) are out of scope for this migration — they integrate at boundaries but are not replaced. cmdk IS in scope and will be replaced by react-aria Autocomplete.
- Form field wrappers (`form/fields/*.field.tsx`) are out of scope — they will be updated in a separate follow-up effort after the base component migration is complete
- The Radix ScrollArea and Resizable components may require separate evaluation as react-aria does not provide direct equivalents
- Migration will happen incrementally per component category, not as a single big-bang change

## Component Migration Inventory

### HIGH priority (P1) — Select (form value selection)

| Current Component | Path | Replacement |
|-------------------|------|-------------|
| React Aria Select | `aria/select.tsx` | Keep (already react-aria) |
| Custom Enum input | `inputs/enum.tsx` | Compose from react-aria Select |

### HIGH priority (P1) — Autocomplete (searchable type-ahead)

| Current Component | Path | Replacement |
|-------------------|------|-------------|
| React Aria Autocomplete | `aria/autocomplete.tsx` | Keep (already react-aria) |
| cmdk-based Combobox | `ui/combobox.tsx` | Migrate to react-aria Autocomplete |
| CMDk Command | `ui/command.tsx` | Migrate to react-aria Autocomplete; remove cmdk dependency |
| Custom Dropdown input | `inputs/dropdown.tsx` | Compose from react-aria Autocomplete |

### HIGH priority (P1) — Menu (action triggering)

| Current Component | Path | Replacement |
|-------------------|------|-------------|
| Radix DropdownMenu | `ui/dropdown-menu.tsx` | react-aria Menu |
| React Aria Menu | `aria/menu.tsx` | Keep (already react-aria) |

### Unchanged — ListBox (standalone selectable list)

| Current Component | Path | Replacement |
|-------------------|------|-------------|
| React Aria ListBox | `aria/list-box.tsx` | Keep (already react-aria, no Radix duplicate) |

### HIGH priority (P1) — Tooltip/Popover

| Current Component | Path | Replacement |
|-------------------|------|-------------|
| Radix Tooltip | `ui/tooltip.tsx` | react-aria Tooltip |
| Radix Popover | `ui/popover.tsx` | react-aria Popover |
| React Aria Tooltip | `aria/tooltip.tsx` | Keep (already react-aria) |
| React Aria Popover | `aria/popover.tsx` | Keep (already react-aria) |

### MEDIUM priority (P2) — Button

| Current Component | Path | Replacement |
|-------------------|------|-------------|
| UI Button | `ui/button.tsx` | react-aria Button + CVA variants |
| Copy buttons | `buttons/copy-to-clipboard.tsx`, `buttons/clipboard.tsx` | Compose Button + useCopyToClipboard hook |
| Info button | `buttons/info-button.tsx` | Button variant="ghost" + icon |
| Link toggle | `buttons/link-toggle-button.tsx` | react-aria ToggleButton or Link |
| Retry button | `buttons/retry.tsx` | Button + retry behavior |

### MEDIUM priority (P2) — Checkbox/Toggle

| Current Component | Path | Replacement |
|-------------------|------|-------------|
| HTML Checkbox | `inputs/checkbox.tsx` | react-aria Checkbox |
| React Aria Checkbox | `aria/checkbox.tsx` | Keep (already react-aria) |

### MEDIUM priority (P2) — Badge/Tag/Pill

| Current Component | Path | Replacement |
|-------------------|------|-------------|
| CVA Badge | `ui/badge.tsx` | Unified Badge with CVA variants |
| Pill | `display/pill.tsx` | Badge variant |
| BadgeCircle | `display/badge-circle.tsx` | Badge variant with dismiss |

### LOWER priority (P3) — Accordion

| Current Component | Path | Replacement |
|-------------------|------|-------------|
| Radix Accordion | `ui/accordion.tsx` | react-aria Disclosure/DisclosureGroup |
| Custom Accordion | `display/accordion.tsx` | react-aria Disclosure |

### LOWER priority (P3) — Modal/Dialog

| Current Component | Path | Replacement |
|-------------------|------|-------------|
| React Aria Modal | `aria/modal.tsx` | Keep (already react-aria) |
| ModalConfirm | `modals/modal-confirm.tsx` | Compose from react-aria Modal |
| ModalDelete | `modals/modal-delete.tsx` | Compose from react-aria Modal |
| SlideOver | `display/slide-over.tsx` | Compose from react-aria Modal |

### LOWER priority (P3) — Tabs

| Current Component | Path | Replacement |
|-------------------|------|-------------|
| Custom Tabs | `tabs.tsx` | react-aria Tabs |
