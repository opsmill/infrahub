/** The two URL lists this module rewrites, always returned together. */
type ColumnNameLists = { hidden: string[]; shown: string[] };

const toggleMembership = (names: readonly string[], field: string): string[] =>
  names.includes(field) ? names.filter((name) => name !== field) : [...names, field];

/**
 * Flips one column, where dropping its name from both lists means "back to the surface's default".
 *
 * Which list a column belongs in is decided by its default: hiding is only ever expressed in
 * `hidden`, revealing only ever in `shown`. That is what keeps a column toggled back to its default
 * out of both params instead of accumulating a contradictory pair and pinning a shared link to what
 * merely happens to be today's default.
 */
export function toggleColumn(
  hidden: readonly string[],
  shown: readonly string[],
  field: string,
  isDefaultVisible: boolean
): ColumnNameLists {
  return isDefaultVisible
    ? { hidden: toggleMembership(hidden, field), shown: [...shown] }
    : { hidden: [...hidden], shown: toggleMembership(shown, field) };
}

/**
 * Hides one column without knowing whether it is visible by default.
 *
 * Deliberately blind to the candidate list: the column-header entry point writes through this, and
 * it has no surface to resolve. Hiding a revealed column drops it from `shown` — the column is then
 * hidden by its own default — and any other column is named in `hidden`, which
 * `getColumnVisibilityState` drops later if the surface hides it by default anyway.
 */
export function hideColumn(
  hidden: readonly string[],
  shown: readonly string[],
  field: string
): ColumnNameLists {
  if (shown.includes(field)) {
    return { hidden: [...hidden], shown: shown.filter((name) => name !== field) };
  }

  return {
    hidden: hidden.includes(field) ? [...hidden] : [...hidden, field],
    shown: [...shown],
  };
}
