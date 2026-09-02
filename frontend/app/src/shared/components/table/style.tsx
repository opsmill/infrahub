/**
 * How wide a column may grow before its contents truncate. Grid tracks sized `auto`
 * have no ceiling, so without a cap one long value stretches the whole column past
 * the viewport. Use with `fit-content()` so short columns still shrink to fit.
 */
export const COLUMN_MAX_WIDTH = "20rem";

/**
 * Cap for identifier columns that stack more than a bare label — a name alongside
 * badges and a description needs more room before truncating.
 */
export const WIDE_COLUMN_MAX_WIDTH = "25rem";

// `min-w-0` lets the cell shrink below its content's intrinsic width, which is what
// makes the `truncate` classes on cell contents actually clip instead of growing the
// column.
export const cellsStyle = "flex min-w-0 items-center gap-1.5 p-2 text-sm h-10";

export const cellHeaderStyle =
  "z-1 sticky top-0 border-r border-y bg-table-cell-pinned disabled:bg-table-cell-pinned font-medium dark:backdrop-blur-md";

export const cellHeaderInteractiveStyle = "hover:bg-highlight";

export const cellBodyStyle = "bg-table-cell border-r border-b dark:group-hover:bg-stone-900";

export const cellFooterStyle =
  "sticky bottom-0 -mt-px h-9 px-2.5 border-t border-r bg-table-cell-pinned";

export const cellMutedStyle = "bg-table-cell text-subtle-muted";
