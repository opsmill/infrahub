import type { VisibilityState } from "@tanstack/react-table";

import type { ColumnField } from "@/entities/nodes/columns/domain/rules/get-column-fields";

/**
 * The single trust boundary for `?hide_columns=` and `?show_columns=`.
 *
 * Both lists arrive from the URL, so either may name a field this schema never had — an old shared
 * link, a kind switch, or a relationship tab reading the same params against a different schema.
 * Such a name is dropped here rather than reaching TanStack, where an unknown column id would
 * silently do nothing. A name that agrees with its surface's default is dropped too: it is not a
 * departure, so it must not count towards the picker's badge or its reset affordance.
 *
 * A name in BOTH params is a contradictory link, and hiding wins. With two named params there is no
 * ordering to fall back on, and hiding is the safer reading: a link that says "hide this" never
 * puts a column the sender meant to keep away on screen.
 */
export function getColumnVisibilityState(
  hiddenNames: readonly string[],
  shownNames: readonly string[],
  columnFields: ColumnField[]
): VisibilityState {
  const defaultVisibilityByName = new Map(
    columnFields.map((field) => [field.name, field.isDefaultVisible])
  );
  const hideRequests = new Set(hiddenNames);

  // Only a default-visible column has anything to hide.
  const hidden = [...hideRequests].filter((name) => defaultVisibilityByName.get(name) === true);
  // Only a default-hidden column has anything to reveal, and never one the other param hides.
  const shown = [...new Set(shownNames)].filter(
    (name) => defaultVisibilityByName.get(name) === false && !hideRequests.has(name)
  );

  return {
    ...Object.fromEntries(shown.map((name) => [name, true] as const)),
    ...Object.fromEntries(hidden.map((name) => [name, false] as const)),
  };
}

/**
 * The revealed field names, validated exactly as the visibility state is and **sorted**: this value
 * feeds a react-query cache key, so `internal_note,owner_note` and `owner_note,internal_note` must
 * produce the same array.
 */
export function getRevealedFields(
  shownNames: readonly string[],
  columnFields: ColumnField[]
): string[] {
  return Object.keys(getColumnVisibilityState([], shownNames, columnFields)).sort();
}
