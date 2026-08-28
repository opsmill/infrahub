import type { VisibilityState } from "@tanstack/react-table";
import { parseAsArrayOf, parseAsString, useQueryStates } from "nuqs";

import { QSP } from "@/shared/config/qsp";

import {
  type ColumnSurface,
  OBJECT_COLUMN_SURFACE,
} from "@/entities/nodes/columns/domain/model/column-surface";
import {
  type ColumnField,
  getColumnFields,
} from "@/entities/nodes/columns/domain/rules/get-column-fields";
import {
  getColumnVisibilityState,
  getRevealedFields,
} from "@/entities/nodes/columns/domain/rules/get-column-visibility-state";
import {
  hideColumn as hideColumnInLists,
  toggleColumn as toggleColumnInLists,
} from "@/entities/nodes/columns/domain/rules/toggle-column";
import type {
  AttributeSchema,
  ModelSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";

const columnNamesParser = parseAsArrayOf(parseAsString).withOptions({ history: "push" });

interface ColumnVisibility {
  /** Every column this surface may offer, in display order — what the picker lists. */
  columnFields: ColumnField[];
  /** TanStack's override map, holding only the departures from the surface's defaults. */
  columnVisibility: VisibilityState;
  /** The revealed default-hidden field names, sorted, so a cache key built from them is stable. */
  revealedFields: string[];
  /** The ordered field schemas a column builder must turn into ColumnDefs. */
  builderFields: Array<AttributeSchema | RelationshipSchema>;
  /** Whether the view departs from the surface's defaults at all — gates the reset affordance. */
  isCustomized: boolean;
  /** How many validated departures the two params name together — what the badge counts. */
  customizedCount: number;
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

  const columnFields = getColumnFields(schema, surface);
  const columnVisibility = getColumnVisibilityState(
    hiddenNamesInQsp,
    shownNamesInQsp,
    columnFields
  );
  // A name both params carry is hidden, not revealed, so it must not reach the fetch either.
  const revealedFields = getRevealedFields(shownNamesInQsp, columnFields).filter(
    (name) => columnVisibility[name] === true
  );
  const builderFields = columnFields
    .filter((field) => field.isDefaultVisible || revealedFields.includes(field.name))
    .map((field) => field.fieldSchema);

  // Writing back the names the trust boundary kept, rather than the ones the URL carried, is what
  // keeps the badge in step with `isCustomized` and stops a stale link's junk from being re-written.
  const hiddenNames = Object.keys(columnVisibility).filter((name) => !columnVisibility[name]);
  const shownNames = revealedFields;

  const setColumns = (next: { hidden: string[]; shown: string[] }) =>
    setColumnsInQsp({
      [QSP.HIDE_COLUMNS]: next.hidden.length > 0 ? next.hidden : null,
      [QSP.SHOW_COLUMNS]: next.shown.length > 0 ? next.shown : null,
    });

  const toggleColumn = (fieldName: string) => {
    const columnField = columnFields.find((field) => field.name === fieldName);
    // The picker only ever offers a candidate, so an unknown name is a no-op rather than a write
    // `getColumnVisibilityState` would immediately drop.
    if (!columnField) return;

    setColumns(
      toggleColumnInLists(hiddenNames, shownNames, fieldName, columnField.isDefaultVisible)
    );
  };

  const hideColumn = (fieldName: string) =>
    setColumns(hideColumnInLists(hiddenNames, shownNames, fieldName));

  const reset = () => setColumnsInQsp({ [QSP.HIDE_COLUMNS]: null, [QSP.SHOW_COLUMNS]: null });

  return {
    columnFields,
    columnVisibility,
    revealedFields,
    builderFields,
    isCustomized: Object.keys(columnVisibility).length > 0,
    customizedCount: Object.keys(columnVisibility).length,
    toggleColumn,
    hideColumn,
    reset,
  };
}
