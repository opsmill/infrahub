# Component Examples Reference

Quick reference pointing to actual component implementations in the codebase.

## Core UI Components

| Component | Path | Description |
|-----------|------|-------------|
| Button | [src/shared/components/buttons/button.tsx](src/shared/components/buttons/button.tsx) | Primary button with CVA variants |
| Input | [src/shared/components/ui/input.tsx](src/shared/components/ui/input.tsx) | Base text input with `inputStyle` |
| Card | [src/shared/components/ui/card.tsx](src/shared/components/ui/card.tsx) | Card container with compound pattern |
| Badge | [src/shared/components/ui/badge.tsx](src/shared/components/ui/badge.tsx) | Status badges with color variants |
| Tooltip | [src/shared/components/ui/tooltip.tsx](src/shared/components/ui/tooltip.tsx) | Radix tooltip wrapper |
| Alert | [src/shared/components/ui/alert.tsx](src/shared/components/ui/alert.tsx) | Alert/notification component |
| Label | [src/shared/components/ui/label.tsx](src/shared/components/ui/label.tsx) | Form label component |
| Spinner | [src/shared/components/ui/spinner.tsx](src/shared/components/ui/spinner.tsx) | Loading spinner |

## Button Variants

| Component | Path | Description |
|-----------|------|-------------|
| Button (base) | [src/shared/components/buttons/button.tsx](src/shared/components/buttons/button.tsx) | CVA variants: primary, outline, danger, ghost |
| CopyToClipboard | [src/shared/components/buttons/copy-to-clipboard.tsx](src/shared/components/buttons/copy-to-clipboard.tsx) | Copy button with feedback |
| InfoButton | [src/shared/components/buttons/info-button.tsx](src/shared/components/buttons/info-button.tsx) | Info icon button |
| Clipboard | [src/shared/components/buttons/clipboard.tsx](src/shared/components/buttons/clipboard.tsx) | Clipboard action button |
| Retry | [src/shared/components/buttons/retry.tsx](src/shared/components/buttons/retry.tsx) | Retry action button |

## Form System

| Component | Path | Description |
|-----------|------|-------------|
| Form (base) | [src/shared/components/ui/form.tsx](src/shared/components/ui/form.tsx) | Form, FormField, FormInput, FormMessage |
| DynamicForm | [src/shared/components/form/dynamic-form.tsx](src/shared/components/form/dynamic-form.tsx) | Schema-driven form |
| ObjectForm | [src/shared/components/form/object-form.tsx](src/shared/components/form/object-form.tsx) | Object CRUD form |
| NodeForm | [src/shared/components/form/node-form.tsx](src/shared/components/form/node-form.tsx) | Node editing form |
| BranchCreateForm | [src/shared/components/form/branch-create-form.tsx](src/shared/components/form/branch-create-form.tsx) | Branch creation form |
| GenericSelector | [src/shared/components/form/generic-selector.tsx](src/shared/components/form/generic-selector.tsx) | Generic entity selector |
| ProfilesSelector | [src/shared/components/form/profiles-selector.tsx](src/shared/components/form/profiles-selector.tsx) | Profile selection |
| PoolSelector | [src/shared/components/form/pool-selector.tsx](src/shared/components/form/pool-selector.tsx) | Resource pool selector |

## Form Fields

| Component | Path | Description |
|-----------|------|-------------|
| InputField | [src/shared/components/form/fields/input.field.tsx](src/shared/components/form/fields/input.field.tsx) | Text input field |
| CheckboxField | [src/shared/components/form/fields/checkbox.field.tsx](src/shared/components/form/fields/checkbox.field.tsx) | Checkbox field |
| DropdownField | [src/shared/components/form/fields/dropdown.field.tsx](src/shared/components/form/fields/dropdown.field.tsx) | Dropdown select field |
| EnumField | [src/shared/components/form/fields/enum.field.tsx](src/shared/components/form/fields/enum.field.tsx) | Enum selector field |
| DatetimeField | [src/shared/components/form/fields/datetime.field.tsx](src/shared/components/form/fields/datetime.field.tsx) | Date/time picker field |
| JsonField | [src/shared/components/form/fields/json.field.tsx](src/shared/components/form/fields/json.field.tsx) | JSON editor field |
| TextareaField | [src/shared/components/form/fields/textarea.field.tsx](src/shared/components/form/fields/textarea.field.tsx) | Multiline text field |
| ColorField | [src/shared/components/form/fields/color.field.tsx](src/shared/components/form/fields/color.field.tsx) | Color picker field |
| PasswordInputField | [src/shared/components/form/fields/password-input.field.tsx](src/shared/components/form/fields/password-input.field.tsx) | Password input field |
| ListField | [src/shared/components/form/fields/list.field.tsx](src/shared/components/form/fields/list.field.tsx) | List/array field |
| PeerField | [src/shared/components/form/fields/peer.field.tsx](src/shared/components/form/fields/peer.field.tsx) | Peer relationship field |
| NodeKindField | [src/shared/components/form/fields/node-kind.field.tsx](src/shared/components/form/fields/node-kind.field.tsx) | Node kind selector |
| RelationshipManyField | [src/shared/components/form/fields/relationships/relationship-many.field.tsx](src/shared/components/form/fields/relationships/relationship-many.field.tsx) | Many-to-many relationships |
| RelationshipHierarchicalField | [src/shared/components/form/fields/relationships/relationship-hierarchical.field.tsx](src/shared/components/form/fields/relationships/relationship-hierarchical.field.tsx) | Hierarchical relationships |
| CommonFieldComponents | [src/shared/components/form/fields/common.tsx](src/shared/components/form/fields/common.tsx) | LabelFormField, shared field utils |

## Inputs

| Component | Path | Description |
|-----------|------|-------------|
| Input | [src/shared/components/ui/input.tsx](src/shared/components/ui/input.tsx) | Base input |
| SearchInput | [src/shared/components/ui/search-input.tsx](src/shared/components/ui/search-input.tsx) | Search with icon |
| PasswordInput | [src/shared/components/ui/password-input.tsx](src/shared/components/ui/password-input.tsx) | Password with toggle |
| Dropdown | [src/shared/components/inputs/dropdown.tsx](src/shared/components/inputs/dropdown.tsx) | Select dropdown |
| Enum | [src/shared/components/inputs/enum.tsx](src/shared/components/inputs/enum.tsx) | Enum selector |
| Checkbox | [src/shared/components/inputs/checkbox.tsx](src/shared/components/inputs/checkbox.tsx) | Checkbox input |
| ColorPicker | [src/shared/components/inputs/color-picker.tsx](src/shared/components/inputs/color-picker.tsx) | Color selection |
| DatePicker | [src/shared/components/inputs/date-picker.tsx](src/shared/components/inputs/date-picker.tsx) | Date selection |
| PoolSelect | [src/shared/components/inputs/pool-select.tsx](src/shared/components/inputs/pool-select.tsx) | Resource pool selector |
| RelationshipMany | [src/shared/components/inputs/relationship-many.tsx](src/shared/components/inputs/relationship-many.tsx) | Multi-relationship input |
| Combobox | [src/shared/components/ui/combobox.tsx](src/shared/components/ui/combobox.tsx) | Searchable select |

## Aria Components (Accessibility)

| Component | Path | Description |
|-----------|------|-------------|
| Checkbox | [src/shared/components/aria/checkbox.tsx](src/shared/components/aria/checkbox.tsx) | React Aria checkbox |
| RadioGroup | [src/shared/components/aria/radio-group.tsx](src/shared/components/aria/radio-group.tsx) | React Aria radio group |
| Label | [src/shared/components/aria/label.tsx](src/shared/components/aria/label.tsx) | React Aria label |
| Separator | [src/shared/components/aria/separator.tsx](src/shared/components/aria/separator.tsx) | React Aria separator |

## Display Components

| Component | Path | Description |
|-----------|------|-------------|
| Avatar | [src/shared/components/display/avatar.tsx](src/shared/components/display/avatar.tsx) | User avatar with initials |
| Badge | [src/shared/components/display/badge.tsx](src/shared/components/display/badge.tsx) | Display badge |
| BadgeCircle | [src/shared/components/display/badge-circle.tsx](src/shared/components/display/badge-circle.tsx) | Circular badge |
| Pill | [src/shared/components/display/pill.tsx](src/shared/components/display/pill.tsx) | Tag/pill component |
| DateDisplay | [src/shared/components/display/date-display.tsx](src/shared/components/display/date-display.tsx) | Formatted date |
| DurationDisplay | [src/shared/components/display/duration-display.tsx](src/shared/components/display/duration-display.tsx) | Time duration |
| ColorDisplay | [src/shared/components/display/color-display.tsx](src/shared/components/display/color-display.tsx) | Color swatch |
| PasswordDisplay | [src/shared/components/display/password-display.tsx](src/shared/components/display/password-display.tsx) | Masked password |
| TextDisplay | [src/shared/components/display/text-display.tsx](src/shared/components/display/text-display.tsx) | Text renderer |
| InlineDisplay | [src/shared/components/display/inline-display.tsx](src/shared/components/display/inline-display.tsx) | Inline content |
| SlideOver | [src/shared/components/display/slide-over.tsx](src/shared/components/display/slide-over.tsx) | Side panel |
| SidepanelTitle | [src/shared/components/display/sidepanel-title.tsx](src/shared/components/display/sidepanel-title.tsx) | Panel title |
| Accordion | [src/shared/components/display/accordion.tsx](src/shared/components/display/accordion.tsx) | Expandable sections |
| PieChart | [src/shared/components/display/pie-chart.tsx](src/shared/components/display/pie-chart.tsx) | Pie chart visualization |
| PropertiesPopover | [src/shared/components/display/properties-popover.tsx](src/shared/components/display/properties-popover.tsx) | Properties tooltip |
| MetaDetailsTooltips | [src/shared/components/display/meta-details-tooltips.tsx](src/shared/components/display/meta-details-tooltips.tsx) | Metadata tooltips |

## Modals

| Component | Path | Description |
|-----------|------|-------------|
| Modal | [src/shared/components/modals/modal.tsx](src/shared/components/modals/modal.tsx) | Base modal |
| ModalDelete | [src/shared/components/modals/modal-delete.tsx](src/shared/components/modals/modal-delete.tsx) | Delete confirmation |
| ModalConfirm | [src/shared/components/modals/modal-confirm.tsx](src/shared/components/modals/modal-confirm.tsx) | Generic confirmation |
| ModalSuccess | [src/shared/components/modals/modal-success.tsx](src/shared/components/modals/modal-success.tsx) | Success message |

## Tables

| Component | Path | Description |
|-----------|------|-------------|
| Table | [src/shared/components/table/table.tsx](src/shared/components/table/table.tsx) | Base table component |
| DataTable | [src/shared/components/table/data-table.tsx](src/shared/components/table/data-table.tsx) | Data grid table |
| PropertyList | [src/shared/components/table/property-list.tsx](src/shared/components/table/property-list.tsx) | Key-value list |
| TableCell | [src/shared/components/table/table-cell.tsx](src/shared/components/table/table-cell.tsx) | Table cell component |
| List | [src/shared/components/table/list.tsx](src/shared/components/table/list.tsx) | List view |
| TableStyles | [src/shared/components/table/style.tsx](src/shared/components/table/style.tsx) | Shared table styles |

## Layout

| Component | Path | Description |
|-----------|------|-------------|
| Content | [src/shared/components/layout/content.tsx](src/shared/components/layout/content.tsx) | Page content wrapper |
| HomeCard | [src/shared/components/ui/home-card.tsx](src/shared/components/ui/home-card.tsx) | Dashboard card |
| Resizable | [src/shared/components/ui/resizable.tsx](src/shared/components/ui/resizable.tsx) | Resizable panels |
| ScrollArea | [src/shared/components/ui/scroll-area.tsx](src/shared/components/ui/scroll-area.tsx) | Custom scrollbar |
| Pagination | [src/shared/components/ui/pagination.tsx](src/shared/components/ui/pagination.tsx) | Page navigation |
| TabsRoutes | [src/shared/components/tabs-routes.tsx](src/shared/components/tabs-routes.tsx) | Routed tabs |

## Loading & Errors

| Component | Path | Description |
|-----------|------|-------------|
| LoadingIndicator | [src/shared/components/loading/loading-indicator.tsx](src/shared/components/loading/loading-indicator.tsx) | Loading state |
| InfrahubLoading | [src/shared/components/loading/infrahub-loading.tsx](src/shared/components/loading/infrahub-loading.tsx) | Branded loading |
| Skeleton | [src/shared/components/skeleton.tsx](src/shared/components/skeleton.tsx) | Skeleton loader |
| TreeSkeleton | [src/shared/components/ui/tree-sheleton.tsx](src/shared/components/ui/tree-sheleton.tsx) | Tree skeleton |
| ErrorScreen | [src/shared/components/errors/error-screen.tsx](src/shared/components/errors/error-screen.tsx) | Error page |
| ErrorFallback | [src/shared/components/errors/error-fallback.tsx](src/shared/components/errors/error-fallback.tsx) | Error boundary fallback |
| ErrorBoundaryApp | [src/shared/components/errors/error-boundary-app.tsx](src/shared/components/errors/error-boundary-app.tsx) | App error boundary |
| ErrorBoundaryRouter | [src/shared/components/errors/error-boundary-router.tsx](src/shared/components/errors/error-boundary-router.tsx) | Router error boundary |
| NoDataFound | [src/shared/components/errors/no-data-found.tsx](src/shared/components/errors/no-data-found.tsx) | Empty state |
| UnauthorizedScreen | [src/shared/components/errors/unauthorized-screen.tsx](src/shared/components/errors/unauthorized-screen.tsx) | 401/403 page |

## Editors

| Component | Path | Description |
|-----------|------|-------------|
| JsonEditor | [src/shared/components/editor/json/json-editor.tsx](src/shared/components/editor/json/json-editor.tsx) | JSON editor |
| CodeViewer | [src/shared/components/editor/code/code-viewer.tsx](src/shared/components/editor/code/code-viewer.tsx) | Code display |
| MarkdownEditor | [src/shared/components/editor/markdown/index.tsx](src/shared/components/editor/markdown/index.tsx) | Markdown editing |
| MarkdownRender | [src/shared/components/editor/markdown/markdown-render.tsx](src/shared/components/editor/markdown/markdown-render.tsx) | Markdown display |
| MarkdownViewer | [src/shared/components/editor/markdown/markdown-viewer.tsx](src/shared/components/editor/markdown/markdown-viewer.tsx) | Read-only markdown |
| CsvTable | [src/shared/components/editor/csv-table.tsx](src/shared/components/editor/csv-table.tsx) | CSV display |

## Stats & Charts

| Component | Path | Description |
|-----------|------|-------------|
| ProgressBarChart | [src/shared/components/stats/progress-bar-chart.tsx](src/shared/components/stats/progress-bar-chart.tsx) | Progress bar |
| MultipleProgressBar | [src/shared/components/stats/multiple-progress-bar.tsx](src/shared/components/stats/multiple-progress-bar.tsx) | Stacked progress |
| PieChart | [src/shared/components/display/pie-chart.tsx](src/shared/components/display/pie-chart.tsx) | Pie chart |

## Other

| Component | Path | Description |
|-----------|------|-------------|
| Kbd | [src/shared/components/ui/kbd.tsx](src/shared/components/ui/kbd.tsx) | Keyboard shortcut |
| Link | [src/shared/components/ui/link.tsx](src/shared/components/ui/link.tsx) | Styled link |
| Id | [src/shared/components/ui/id.tsx](src/shared/components/ui/id.tsx) | ID display |
| BadgeCopy | [src/shared/components/ui/badge-copy.tsx](src/shared/components/ui/badge-copy.tsx) | Copyable badge |
| Pulse | [src/shared/components/ui/pulse.tsx](src/shared/components/ui/pulse.tsx) | Pulse animation |
| TimelineBorder | [src/shared/components/ui/timeline-border.tsx](src/shared/components/ui/timeline-border.tsx) | Timeline line |
| DropdownMenu | [src/shared/components/ui/dropdown-menu.tsx](src/shared/components/ui/dropdown-menu.tsx) | Action menu |
| Popover | [src/shared/components/ui/popover.tsx](src/shared/components/ui/popover.tsx) | Popover container |
| Command | [src/shared/components/ui/command.tsx](src/shared/components/ui/command.tsx) | Command palette |
| Download | [src/shared/components/download.tsx](src/shared/components/download.tsx) | Download trigger |
| InfiniteTrigger | [src/shared/components/utils/infinite-trigger.tsx](src/shared/components/utils/infinite-trigger.tsx) | Infinite scroll |
| Comment | [src/shared/components/conversations/comment.tsx](src/shared/components/conversations/comment.tsx) | Comment display |
| AddComment | [src/shared/components/conversations/add-comment.tsx](src/shared/components/conversations/add-comment.tsx) | Comment form |
| TasksFilterForm | [src/shared/components/filters/tasks-filter-form.tsx](src/shared/components/filters/tasks-filter-form.tsx) | Task filtering |

## Utilities

| Utility | Path | Description |
|---------|------|-------------|
| classNames | [src/shared/utils/common.ts](src/shared/utils/common.ts) | clsx + tailwind-merge |
| focusVisibleStyle | [src/shared/utils/common.ts](src/shared/utils/common.ts) | Focus ring styles |
| focusWithinStyle | [src/shared/utils/common.ts](src/shared/utils/common.ts) | Focus-within styles |
| inputStyle | [src/shared/components/ui/input.tsx](src/shared/components/ui/input.tsx) | Base input classes |

## Configuration

| File | Path | Description |
|------|------|-------------|
| Tailwind Config | [tailwind.config.js](tailwind.config.js) | Theme, colors, plugins |
| TypeScript Config | [tsconfig.json](tsconfig.json) | TS settings, path aliases |
| Biome Config | [biome.jsonc](biome.jsonc) | Formatting rules |
| Vite Config | [vite.config.ts](vite.config.ts) | Build configuration |
