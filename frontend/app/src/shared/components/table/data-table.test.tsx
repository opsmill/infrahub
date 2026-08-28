import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";
import { describe, expect, test } from "vitest";

import { render } from "../../../../tests/components/render";
import { DataTable } from "./data-table";

interface TestRow {
  id: string;
  name: string;
  __typename: string;
}

const columnHelper = createColumnHelper<TestRow>();

// Mirrors the real object table's shape: an identity column, one schema field
// column, the kind column and the actions column.
const columns: Array<ColumnDef<TestRow, unknown>> = [
  columnHelper.display({
    id: "id",
    header: () => <div>Identifier</div>,
    cell: ({ row }) => <div>{row.original.id}</div>,
  }),
  columnHelper.display({
    id: "name",
    header: () => <div>Device name</div>,
    cell: ({ row }) => <div>{row.original.name}</div>,
  }),
  columnHelper.display({
    id: "objectKind",
    header: () => <div>Kind</div>,
    cell: ({ row }) => <div>{row.original.__typename}</div>,
  }),
  columnHelper.display({
    id: "actions",
    header: () => <div>Actions</div>,
    cell: () => <div>Edit</div>,
  }),
];

const data: Array<TestRow> = [{ id: "device-1", name: "atl1-core1", __typename: "InfraDevice" }];

describe("DataTable", () => {
  test("renders a header for every column when no visibility state is given", async () => {
    // GIVEN
    const columnVisibility = undefined;

    // WHEN
    const component = await render(
      <DataTable columns={columns} data={data} columnVisibility={columnVisibility} />
    );

    // THEN
    await expect.element(component.getByText("Identifier")).toBeVisible();
    await expect.element(component.getByText("Device name")).toBeVisible();
    await expect.element(component.getByText("Kind")).toBeVisible();
    await expect.element(component.getByText("Actions")).toBeVisible();
  });

  test("omits both the header and the body cell of a column hidden by the visibility state", async () => {
    // GIVEN
    const columnVisibility = { name: false };

    // WHEN
    const component = await render(
      <DataTable columns={columns} data={data} columnVisibility={columnVisibility} />
    );

    // THEN
    await expect.element(component.getByText("Identifier")).toBeVisible();
    expect(component.getByText("Device name").elements()).toHaveLength(0);
    expect(component.getByText("atl1-core1").elements()).toHaveLength(0);
  });

  test("keeps the header and the body cell of a column explicitly set to visible", async () => {
    // GIVEN
    const columnVisibility = { name: true };

    // WHEN
    const component = await render(
      <DataTable columns={columns} data={data} columnVisibility={columnVisibility} />
    );

    // THEN
    await expect.element(component.getByText("Device name")).toBeVisible();
    await expect.element(component.getByText("atl1-core1")).toBeVisible();
  });

  test("derives gridTemplateColumns from the visible column count only", async () => {
    // GIVEN
    const columnVisibility = { name: false };

    // WHEN
    const component = await render(
      <DataTable
        columns={columns}
        data={data}
        columnVisibility={columnVisibility}
        role="grid"
        aria-label="Devices"
      />
    );

    // THEN
    const grid = component.getByRole("grid", { name: "Devices" }).element() as HTMLElement;
    // 3 of the 4 columns are visible, so the default formula
    // `repeat(columnCount - 2, auto) 1fr 2.5rem` must lay out 3 tracks — one
    // track per rendered cell. A 4th (phantom) track misaligns every row.
    expect(grid.style.gridTemplateColumns).toBe("repeat(1, auto) 1fr 2.5rem");
  });

  test("keeps the identity column when every other column is hidden", async () => {
    // GIVEN
    const columnVisibility = { name: false, objectKind: false, actions: false };

    // WHEN
    const component = await render(
      <DataTable columns={columns} data={data} columnVisibility={columnVisibility} />
    );

    // THEN
    await expect.element(component.getByText("Identifier")).toBeVisible();
    await expect.element(component.getByText("device-1")).toBeVisible();
  });

  test("renders one footer count cell per visible column", async () => {
    // GIVEN
    const columnVisibility = { name: false };

    // WHEN
    const component = await render(
      <DataTable
        columns={columns}
        data={data}
        count={42}
        columnVisibility={columnVisibility}
        role="grid"
        aria-label="Devices"
      />
    );

    // THEN
    const grid = component.getByRole("grid", { name: "Devices" }).element();
    // Footer cells carry no accessible role, so their number can only be read
    // from the `cellFooterStyle` sticky-bottom class they alone carry.
    expect(grid.querySelectorAll(":scope > .bottom-0")).toHaveLength(3);
  });
});
