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

// A column change replaces the current history entry, so Back does not undo it.
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
   * True even when every name in them is unknown to this schema and no column on screen departs
   * from its default: the params are still sticky, still shared in a link, and still need clearing.
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
 * Reads `?hide_columns=` and `?show_columns=`, each a plain list of field names.
 *
 * Both params absent is the surface's default, so a write drops a list that came out empty rather
 * than writing an empty one — a shared link must never pin a table to today's default.
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
  // Annotated with the table library's own type so `domain/` never has to import it.
  const columnVisibility: VisibilityState = getColumnVisibilityState(
    hiddenNamesInQsp,
    shownNamesInQsp,
    columnCandidates
  );
  // Derived from the validated state so it cannot drift from what the table renders.
  const revealedFields = getRevealedFields(columnVisibility);
  const columnSchemas = columnCandidates
    .filter((field) => field.isDefaultVisible || revealedFields.includes(field.name))
    .map((field) => field.fieldSchema);

  // The names a write echoes back are the validated ones, so a stale link's junk leaves the URL
  // on the next toggle instead of being re-written.
  const hiddenNames = Object.keys(columnVisibility).filter((name) => !columnVisibility[name]);
  const shownNames = revealedFields;

  const setColumns = (next: { hidden: string[]; shown: string[] }) =>
    setColumnsInQsp({
      [QSP.HIDE_COLUMNS]: next.hidden.length > 0 ? next.hidden : null,
      [QSP.SHOW_COLUMNS]: next.shown.length > 0 ? next.shown : null,
    });

  const toggleColumn = (fieldName: string) => {
    const columnCandidate = columnCandidates.find((field) => field.name === fieldName);
    // A name this schema has no column for is a no-op rather than a param that gets dropped anyway.
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
    // `null` is an absent param, while `?p=` yields `[]` — present, empty, and still clearable.
    hasColumnParamsInUrl:
      columnsInQsp[QSP.HIDE_COLUMNS] !== null || columnsInQsp[QSP.SHOW_COLUMNS] !== null,
    toggleColumn,
    hideColumn,
    reset,
  };
}
