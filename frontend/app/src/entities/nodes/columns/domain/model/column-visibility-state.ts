/**
 * The override map a table applies on top of its surface's defaults: one entry per column that
 * departs from its default, `true` for revealed and `false` for hidden. A column neither param names
 * is absent, which is what makes the map a delta rather than a snapshot.
 *
 * Declared here rather than imported from a table library so `domain/` stays renderer-agnostic — a
 * TUI or a CLI reads the same map. It is structurally identical to TanStack's `VisibilityState`, and
 * `ui/hooks` is the one place the two names are allowed to meet.
 */
export type ColumnVisibilityState = Record<string, boolean>;
