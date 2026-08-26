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
export const cellsStyle =
  "flex min-w-0 items-center gap-1.5 p-2 text-sm h-10 bg-white disabled:bg-white";

export const cellHeaderStyle =
  "z-1 sticky top-0 border-r border-y border-gray-200 hover:bg-gray-100 font-medium";

export const cellBodyStyle = "bg-gray-50 border-r border-b border-gray-200";

export const cellFooterStyle =
  "sticky bottom-0 -mt-px h-9 border-gray-200 px-2.5 border-t border-r";

export const cellMutedStyle = "bg-gray-50 text-gray-400";
