import type { ColumnVisibilityState } from "@/entities/nodes/columns/domain/model/column-visibility-state";
import type { ColumnField } from "@/entities/nodes/columns/domain/rules/get-column-fields";

/**
 * The single trust boundary for `?hide_columns=` and `?show_columns=`.
 *
 * Both lists arrive from the URL, so either may name a field this schema never had — an old shared
 * link, a kind switch, or a relationship tab reading the same params against a different schema.
 * Such a name is dropped here rather than reaching the table, where an unknown column id would
 * silently do nothing. A name that agrees with its surface's default is dropped too: it is not a
 * departure, so it must not count towards the picker's badge.
 *
 * A name in BOTH params is a contradictory link, and hiding wins. With two named params there is no
 * ordering to fall back on, and hiding is the safer reading: a link that says "hide this" never
 * puts a column the sender meant to keep away on screen.
 *
 * At least one field column always survives — see `keepOneFieldColumnVisible`.
 */
export function getColumnVisibilityState(
  hiddenNames: readonly string[],
  shownNames: readonly string[],
  columnFields: ColumnField[]
): ColumnVisibilityState {
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

  const visibility: ColumnVisibilityState = {
    ...Object.fromEntries(shown.map((name) => [name, true] as const)),
    ...Object.fromEntries(hidden.map((name) => [name, false] as const)),
  };

  return keepOneFieldColumnVisible(visibility, columnFields);
}

/**
 * The minimum: a table never ends up with zero field columns.
 *
 * **The rule.** If applying the hide list would leave no field column visible, exactly one hide
 * entry is dropped — the one for the FIRST column in `columnFields` display order that the hide list
 * names. That column returns to its default, which is necessarily visible, since only a
 * default-visible column ever gets a `false` entry. Every other hide entry is kept, so as little of
 * the request is discarded as possible. Display order, not param order, decides the survivor: the
 * same set of names must always leave the same column standing, however the URL happens to spell it.
 *
 * **Why here.** This is the single trust boundary, so it is the only place that can hold for BOTH
 * ways zero columns can be asked for: the picker unchecking the last box, and a hand-written or
 * stale `?hide_columns=` naming every column at once. Enforcing it in the picker would leave the
 * crafted URL unguarded; enforcing it in the table would leave the URL and the screen disagreeing.
 * The picker still greys out the last remaining item, so the clamp is never what a user meets — that
 * is an affordance on top of this rule, not a second copy of it.
 *
 * **Why at all.** The IPAM tables render an "available range" row as one cell spanning
 * `col-start-2 -col-end-2`, which needs a grid track between the identity and actions columns; with
 * every field column hidden the two grid lines collapse onto each other and the row wraps. Beyond
 * that one symptom, a table showing only a row label and an actions menu carries no data and gives
 * the user nothing to click back from except Reset.
 *
 * A surface offering nothing but default-hidden columns has no hide entry to give back and is
 * returned untouched: there is no hide request to blame for the empty table, so there is none to
 * relax.
 */
function keepOneFieldColumnVisible(
  visibility: ColumnVisibilityState,
  columnFields: ColumnField[]
): ColumnVisibilityState {
  const isVisible = ({ name, isDefaultVisible }: ColumnField) =>
    name in visibility ? visibility[name] : isDefaultVisible;
  if (columnFields.some(isVisible)) return visibility;

  const survivor = columnFields.find(({ name }) => visibility[name] === false);
  if (!survivor) return visibility;

  const { [survivor.name]: _restored, ...withSurvivorVisible } = visibility;

  return withSurvivorVisible;
}

/**
 * The revealed field names, read straight off the state above and **sorted**: this value feeds a
 * react-query cache key, so `internal_note,owner_note` and `owner_note,internal_note` must produce
 * the same array.
 */
export function getRevealedFields(visibility: ColumnVisibilityState): string[] {
  return Object.keys(visibility)
    .filter((name) => visibility[name])
    .sort();
}
