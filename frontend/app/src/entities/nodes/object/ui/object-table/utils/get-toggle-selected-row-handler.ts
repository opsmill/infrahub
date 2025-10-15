import type { CellContext } from "@tanstack/react-table";
import type { PressEvent } from "react-aria-components";

import type { NodeCore } from "@/entities/nodes/types";

export function getToggleSelectedRowHandler<T extends NodeCore>({
  row,
  table,
}: Pick<CellContext<T, string>, "row" | "table">) {
  return (e: PressEvent): void => {
    if (!e.shiftKey) {
      row.toggleSelected();
      return;
    }

    const selectedRows = table.getSelectedRowModel().flatRows;
    const lastSelectedRow = selectedRows.at(-1);

    if (!lastSelectedRow) {
      row.toggleSelected();
      return;
    }

    const currentRowIndex = row.index;
    const lastSelectedRowIndex = lastSelectedRow.index;

    const start = Math.min(currentRowIndex, lastSelectedRowIndex);
    const end = Math.max(currentRowIndex, lastSelectedRowIndex);

    const rowsToToggle = table.getRowModel().flatRows.slice(start, end + 1);
    const isCellSelected = row.getIsSelected();
    rowsToToggle.forEach((row) => row.toggleSelected(!isCellSelected));
  };
}
