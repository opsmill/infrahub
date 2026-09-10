import type { ColumnVisibilityState } from "@/entities/nodes/columns/domain/model/column-visibility-state";
import type { ColumnCandidate } from "@/entities/nodes/columns/domain/rules/get-column-candidates";

/**
 * The single trust boundary for `?hide_columns=` and `?show_columns=`.
 *
 * Both lists arrive from the URL, so either may name a field this schema never had — an old shared
 * link, a kind switch, or a relationship tab reading the same params against a different schema.
 * Such a name is dropped here rather than reaching the table, where an unknown column id would
 * silently do nothing. A name that agrees with its surface's default is dropped too: it is not a
 * departure, so it must not count towards the picker's badge.
 *
 * A name in BOTH params is a contradictory link, and hiding wins: with two named params there is no
 * ordering to fall back on, and a link that says "hide this" must never put that column on screen.
 *
 * A hide request cannot take away the last visible field column. A surface offering nothing but
 * default-hidden columns is a different case and is returned unchanged: nothing was hidden, so
 * there is no hide request to relax.
 */
export function getColumnVisibilityState(
  hiddenNames: readonly string[],
  shownNames: readonly string[],
  columnCandidates: ColumnCandidate[]
): ColumnVisibilityState {
  const defaultVisibilityByName = new Map(
    columnCandidates.map((field) => [field.name, field.isDefaultVisible])
  );
  const hideRequests = new Set(hiddenNames);

  // Only a default-hidden column has anything to reveal, and never one the other param hides.
  const shown = shownNames.filter(
    (name) => defaultVisibilityByName.get(name) === false && !hideRequests.has(name)
  );
  // Only a default-visible column has anything to hide.
  const hidden = [...hideRequests].filter((name) => defaultVisibilityByName.get(name) === true);

  // Assigned onto a null prototype rather than spread into a literal: a spread would produce an
  // ordinary object, on which a field named after an `Object.prototype` member reads as present.
  const visibility: ColumnVisibilityState = Object.assign(
    Object.create(null),
    Object.fromEntries(shown.map((name) => [name, true])),
    Object.fromEntries(hidden.map((name) => [name, false]))
  );

  return keepOneFieldColumnVisible(visibility, columnCandidates);
}

/**
 * Drops one hide entry when the hide list would leave no field column visible, so the state can
 * never empty a table. Display order picks which, so the same set of names always leaves the same
 * column standing however the URL spells them.
 */
function keepOneFieldColumnVisible(
  visibility: ColumnVisibilityState,
  columnCandidates: ColumnCandidate[]
): ColumnVisibilityState {
  const isVisible = ({ name, isDefaultVisible }: ColumnCandidate) =>
    name in visibility ? visibility[name] : isDefaultVisible;
  if (columnCandidates.some(isVisible)) return visibility;

  const survivor = columnCandidates.find(({ name }) => visibility[name] === false);
  // Nothing was hidden, so there is no hide request to relax.
  if (!survivor) return visibility;

  const withSurvivorVisible: ColumnVisibilityState = Object.create(null);
  for (const [name, isVisible] of Object.entries(visibility)) {
    if (name !== survivor.name) withSurvivorVisible[name] = isVisible;
  }

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
