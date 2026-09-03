/**
 * The override map a table applies on top of its surface's defaults: one entry per column that
 * departs from its default, `true` for revealed and `false` for hidden. A column neither param names
 * is absent, which is what makes the map a delta rather than a snapshot.
 */
export type ColumnVisibilityState = Record<string, boolean>;
