import type { VisibilityState } from "@tanstack/react-table";
import { parseAsArrayOf, parseAsString, useQueryStates } from "nuqs";

import { QSP } from "@/shared/config/qsp";

import type { ColumnSurface } from "@/entities/nodes/columns/domain/model/column-surface";
import { OBJECT_COLUMN_SURFACE } from "@/entities/nodes/columns/domain/rules/column-surfaces";
import {
  type ColumnCandidate,
  getColumnCandidates,
} from "@/entities/nodes/columns/domain/rules/get-column-candidates";
import {
  getColumnVisibilityState,
  getRevealedFields,
} from "@/entities/nodes/columns/domain/rules/get-column-visibility-state";
import {
  hideColumn as hideColumnInLists,
  toggleColumn as toggleColumnInLists,
} from "@/entities/nodes/columns/domain/rules/toggle-column";
import type { FieldSchema, ModelSchema } from "@/entities/schema/domain/model/schema";

// `replace`, not `push` — a tradeoff, not a free win. A checklist invites several toggles in a row,
// and under `push` each one costs a separate Back press to undo. Under `replace` no column change is
// undoable by Back at all: the way back is Reset, or re-toggling. We take that because per-toggle
// history entries bury the page the user arrived from. The params travel in a shared link either way.
const columnNamesParser = parseAsArrayOf(parseAsString).withOptions({ history: "replace" });

interface ColumnVisibility {
  /** Every column this surface may offer, in display order — what the picker lists. */
  columnCandidates: ColumnCandidate[];
  /** TanStack's override map, holding only the departures from the surface's defaults. */
  columnVisibility: VisibilityState;
  /** The revealed default-hidden field names, sorted, so a cache key built from them is stable. */
  revealedFields: string[];
  /** The ordered field schemas a column builder must turn into ColumnDefs. */
  columnSchemas: FieldSchema[];
  /** How many validated departures from the surface's defaults there are — what the badge counts. */
  customizedColumnCount: number;
  /**
   * Whether either param is in the URL at all, junk included — what gates the reset affordance.
   *
   * Deliberately NOT `customizedColumnCount > 0`. After a kind switch the params can name only fields the
   * new schema lacks; the trust boundary then drops every one, so nothing renders wrong and the
   * badge correctly counts zero — but the params are still there, still sticky, and still travelling
   * in any link the user shares. Reset has to stay reachable to clear them.
   */
  hasColumnParamsInUrl: boolean;
  /** Flip one column, dropping its name from both params when it is back at its default. */
  toggleColumn: (fieldName: string) => void;
  /** Hide one column, whatever this surface's default for it turns out to be. */
  hideColumn: (fieldName: string) => void;
  /** Drop both params, restoring the surface's defaults. */
  reset: () => void;
}

/**
 * The one hook reading `?hide_columns=` and `?show_columns=`, each a plain list of field names.
 *
 * Two named params instead of one prefixed list: a comma-separated list of names survives nuqs's
 * encoder untouched, so a shared link stays readable, and there is no prefix convention to learn.
 * Both params absent is the surface's default, so every write drops a list that came out empty
 * rather than writing an empty one — a shared link must never pin a table to what merely happens to
 * be today's default.
 */
export function useColumnVisibility(
  schema: ModelSchema,
  surface: ColumnSurface = OBJECT_COLUMN_SURFACE
): ColumnVisibility {
  const [columnsInQsp, setColumnsInQsp] = useQueryStates({
    [QSP.HIDE_COLUMNS]: columnNamesParser,
    [QSP.SHOW_COLUMNS]: columnNamesParser,
  });

  const hiddenNamesInQsp = columnsInQsp[QSP.HIDE_COLUMNS] ?? [];
  const shownNamesInQsp = columnsInQsp[QSP.SHOW_COLUMNS] ?? [];

  const columnCandidates = getColumnCandidates(schema, surface);
  // TanStack names this shape `VisibilityState`; the domain calls it `ColumnVisibilityState`. This
  // annotation is the one place the two vocabularies meet, which is what keeps the table library out
  // of `domain/` while consumers still get the type TanStack's `state` option expects.
  const columnVisibility: VisibilityState = getColumnVisibilityState(
    hiddenNamesInQsp,
    shownNamesInQsp,
    columnCandidates
  );
  // Read off the state above rather than re-derived from the params: one pass through the trust
  // boundary per render, and the two values cannot drift apart.
  const revealedFields = getRevealedFields(columnVisibility);
  const columnSchemas = columnCandidates
    .filter((field) => field.isDefaultVisible || revealedFields.includes(field.name))
    .map((field) => field.fieldSchema);

  // Writing back the names the trust boundary kept, rather than the ones the URL carried, is what
  // keeps the badge in step with what is on screen and stops a stale link's junk from being
  // re-written. A write is also how that junk finally leaves the URL.
  const hiddenNames = Object.keys(columnVisibility).filter((name) => !columnVisibility[name]);
  const shownNames = revealedFields;

  const setColumns = (next: { hidden: string[]; shown: string[] }) =>
    setColumnsInQsp({
      [QSP.HIDE_COLUMNS]: next.hidden.length > 0 ? next.hidden : null,
      [QSP.SHOW_COLUMNS]: next.shown.length > 0 ? next.shown : null,
    });

  const toggleColumn = (fieldName: string) => {
    const columnCandidate = columnCandidates.find((field) => field.name === fieldName);
    // The picker only ever offers a candidate, so an unknown name is a no-op rather than a write
    // `getColumnVisibilityState` would immediately drop.
    if (!columnCandidate) return;

    setColumns(
      toggleColumnInLists(hiddenNames, shownNames, fieldName, columnCandidate.isDefaultVisible)
    );
  };

  const hideColumn = (fieldName: string) =>
    setColumns(hideColumnInLists(hiddenNames, shownNames, fieldName));

  const reset = () => setColumnsInQsp({ [QSP.HIDE_COLUMNS]: null, [QSP.SHOW_COLUMNS]: null });

  return {
    columnCandidates,
    columnVisibility,
    revealedFields,
    columnSchemas,
    customizedColumnCount: Object.keys(columnVisibility).length,
    // The raw query state, not the validated lists: `null` means the param is absent, and `?p=`
    // yields `[]`, which is a present-but-empty param the user should still be able to clear.
    hasColumnParamsInUrl:
      columnsInQsp[QSP.HIDE_COLUMNS] !== null || columnsInQsp[QSP.SHOW_COLUMNS] !== null,
    toggleColumn,
    hideColumn,
    reset,
  };
}
