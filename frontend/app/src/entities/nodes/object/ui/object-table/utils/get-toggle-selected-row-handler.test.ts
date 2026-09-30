import {
  createTable,
  functionalUpdate,
  getCoreRowModel,
  type TableState,
} from "@tanstack/react-table";
import type { PressEvent } from "react-aria-components";
import { describe, expect, it } from "vitest";

import { getToggleSelectedRowHandler } from "./get-toggle-selected-row-handler";

interface Row {
  id: string;
}

function createRowsTable(initialIds: string[]) {
  let data: Row[] = initialIds.map((id) => ({ id }));
  const table = createTable<Row>({
    data,
    columns: [],
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id,
    enableRowSelection: true,
    state: {},
    onStateChange: () => {},
    renderFallbackValue: null,
  });
  let state: TableState = table.initialState;

  const sync = () => {
    table.setOptions((prev) => ({
      ...prev,
      data,
      state,
      onStateChange: (updater) => {
        state = functionalUpdate(updater, state);
        sync();
      },
    }));
  };
  sync();

  return {
    table,
    setIds: (ids: string[]) => {
      data = ids.map((id) => ({ id }));
      sync();
    },
    press: (id: string, { shiftKey = false } = {}) => {
      getToggleSelectedRowHandler({ row: table.getRow(id), table })({ shiftKey } as PressEvent);
    },
    selectedIds: () => table.getSelectedRowModel().flatRows.map((row) => row.id),
  };
}

describe("getToggleSelectedRowHandler", () => {
  it("toggles only the clicked row on a plain click", () => {
    // GIVEN
    const rows = createRowsTable(["a", "b", "c"]);

    // WHEN
    rows.press("b");

    // THEN
    expect(rows.selectedIds()).toEqual(["b"]);
  });

  it("unselects a selected row on a second plain click", () => {
    // GIVEN
    const rows = createRowsTable(["a", "b", "c"]);
    rows.press("b");

    // WHEN
    rows.press("b");

    // THEN
    expect(rows.selectedIds()).toEqual([]);
  });

  it("selects the range between the last-selected row and the shift-clicked one", () => {
    // GIVEN
    const rows = createRowsTable(["a", "b", "c", "d", "e"]);
    rows.press("b");

    // WHEN
    rows.press("d", { shiftKey: true });

    // THEN
    expect(rows.selectedIds()).toEqual(["b", "c", "d"]);
  });

  it("deselects the range when the shift-clicked row is selected", () => {
    // GIVEN
    const rows = createRowsTable(["a", "b", "c", "d", "e"]);
    rows.press("a");
    rows.press("e", { shiftKey: true });
    rows.press("b");

    // WHEN
    rows.press("d", { shiftKey: true });

    // THEN
    expect(rows.selectedIds()).toEqual(["a", "e"]);
  });

  it("toggles only the clicked row when the first-ever click is a shift-click", () => {
    // GIVEN
    const rows = createRowsTable(["a", "b", "c", "d", "e"]);

    // WHEN
    rows.press("d", { shiftKey: true });

    // THEN
    expect(rows.selectedIds()).toEqual(["d"]);
  });

  it("ranges from the same row by id after rows are inserted above it", () => {
    // GIVEN
    const rows = createRowsTable(["a", "b", "c", "d", "e"]);
    rows.press("c");
    rows.setIds(["x", "y", "a", "b", "c", "d", "e"]);

    // WHEN
    rows.press("e", { shiftKey: true });

    // THEN
    expect(rows.selectedIds()).toEqual(["c", "d", "e"]);
  });

  it("falls back to a plain toggle when the last-selected row no longer exists", () => {
    // GIVEN
    const rows = createRowsTable(["a", "b", "c", "d", "e"]);
    rows.press("c");
    rows.setIds(["a", "b", "d", "e"]);

    // WHEN
    rows.press("e", { shiftKey: true });

    // THEN
    expect(rows.selectedIds()).toEqual(["e"]);
  });

  it("keeps an independent anchor per table", () => {
    // GIVEN
    const first = createRowsTable(["a", "b", "c", "d"]);
    const second = createRowsTable(["a", "b", "c", "d"]);
    first.press("a");
    second.press("c");

    // WHEN
    first.press("b", { shiftKey: true });

    // THEN
    expect(first.selectedIds()).toEqual(["a", "b"]);
    expect(second.selectedIds()).toEqual(["c"]);
  });
});
