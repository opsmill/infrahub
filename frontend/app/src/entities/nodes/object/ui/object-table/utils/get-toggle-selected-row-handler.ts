import type { CellContext } from "@tanstack/react-table";
import type { PressEvent } from "react-aria-components";

// Ids, not indexes: rows can be inserted above the last-selected one between two clicks.
const lastSelectedIdByTable = new WeakMap<object, string>();

export function getToggleSelectedRowHandler<T>({
  row,
  table,
}: Pick<CellContext<T, string>, "row" | "table">) {
  return (e: PressEvent): void => {
    const lastSelectedId = lastSelectedIdByTable.get(table);
    const lastSelectedRow =
      e.shiftKey && lastSelectedId !== undefined
        ? table.getRowModel().rowsById[lastSelectedId]
        : undefined;
    lastSelectedIdByTable.set(table, row.id);

    if (!lastSelectedRow) {
      row.toggleSelected();
      return;
    }

    const start = Math.min(row.index, lastSelectedRow.index);
    const end = Math.max(row.index, lastSelectedRow.index);

    const rowsToToggle = table.getRowModel().flatRows.slice(start, end + 1);
    const isCellSelected = row.getIsSelected();
    rowsToToggle.forEach((row) => row.toggleSelected(!isCellSelected));
  };
}
