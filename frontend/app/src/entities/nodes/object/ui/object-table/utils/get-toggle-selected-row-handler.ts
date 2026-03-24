import type { CellContext } from "@tanstack/react-table";
import type { PressEvent } from "react-aria-components";

import type { NodeCore } from "@/entities/nodes/types";

const lastSelectedIndexByTable = new WeakMap<object, number>();

export function getToggleSelectedRowHandler<T extends NodeCore>({
  row,
  table,
}: Pick<CellContext<T, string>, "row" | "table">) {
  return (e: PressEvent): void => {
    if (!e.shiftKey) {
      row.toggleSelected();
      lastSelectedIndexByTable.set(table, row.index);
      return;
    }

    const lastSelectedRowIndex = lastSelectedIndexByTable.get(table);

    if (lastSelectedRowIndex === undefined) {
      row.toggleSelected();
      lastSelectedIndexByTable.set(table, row.index);
      return;
    }

    const currentRowIndex = row.index;

    const start = Math.min(currentRowIndex, lastSelectedRowIndex);
    const end = Math.max(currentRowIndex, lastSelectedRowIndex);

    const rowsToToggle = table.getRowModel().flatRows.slice(start, end + 1);
    const isCellSelected = row.getIsSelected();
    rowsToToggle.forEach((row) => row.toggleSelected(!isCellSelected));
    lastSelectedIndexByTable.set(table, row.index);
  };
}
