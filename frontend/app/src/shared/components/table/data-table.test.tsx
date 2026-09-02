import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";
import { describe, expect, test } from "vitest";

import { DataTable } from "@/shared/components/table/data-table";
import { COLUMN_MAX_WIDTH } from "@/shared/components/table/style";

import {
  StickyLeftCell,
  StickyRightCell,
} from "@/entities/nodes/object/ui/object-table/cells/style";
import { TableIdentifierCell } from "@/entities/nodes/object/ui/object-table/cells/table-identifier-cell";

import { render } from "../../../../tests/components/render";
import { initPointerTracking } from "../../../../tests/components/utils";

// A single unbreakable token is the worst case: its min-content width equals its
// max-content width, so nothing but a capped grid track can keep it in bounds.
const LONG_LABEL =
  "core-aggregation-switch-amsterdam-east-campus-distribution-layer-replacing-the-decommissioned-nexus-pair";
const SHORT_LABEL = "atl1-core1";

interface DemoRow {
  id: string;
  __typename: string;
  label: string;
}

const buildColumns = (
  label: (row: DemoRow) => React.ReactNode,
  tooltipLabel?: string
): ColumnDef<DemoRow>[] => [
  {
    id: "identifier",
    header: () => <StickyLeftCell>Name</StickyLeftCell>,
    cell: ({ row }) => (
      <TableIdentifierCell
        objectKind="TestingOverflowDemo"
        objectId={row.original.id}
        label={label(row.original)}
        tooltipLabel={tooltipLabel}
      />
    ),
  },
  {
    id: "description",
    header: () => <div>Description</div>,
    cell: () => <div>a description</div>,
  },
  {
    id: "status",
    header: () => <div>Status</div>,
    cell: () => <div>active</div>,
  },
  {
    id: "actions",
    header: () => <div />,
    cell: () => <StickyRightCell data-testid="actions-cell">...</StickyRightCell>,
  },
];

const columns = buildColumns((row) => row.label);

const rows: DemoRow[] = [
  { id: "1", __typename: "TestingOverflowDemo", label: SHORT_LABEL },
  { id: "2", __typename: "TestingOverflowDemo", label: LONG_LABEL },
];

// The narrow, horizontally scrollable wrapper is what makes this a real test: it is
// the container the sticky cells pin against, and the one the first column must not
// outgrow.
const renderTable = (columnDefs: ColumnDef<DemoRow>[], data: DemoRow[]) =>
  render(
    <div className="w-[600px] overflow-x-auto">
      <DataTable columns={columnDefs} data={data} />
    </div>
  );

const identifierCells = () =>
  Array.from(document.querySelectorAll('[data-testid="identifier-cell"]'));

describe("DataTable first column overflow", () => {
  test("caps the first column instead of letting it grow with its content", async () => {
    // GIVEN
    await renderTable(columns, rows);

    // THEN
    const cells = identifierCells();
    expect(cells).toHaveLength(2);

    // Unconstrained, this renders at ~800px. The bound is deliberately loose so the
    // test tracks "a cap exists", not the exact cap value.
    expect(cells[1]!.getBoundingClientRect().width).toBeLessThanOrEqual(400);
  });

  test("keeps the column shrink-to-fit rather than padding it out to the cap", async () => {
    // GIVEN
    await renderTable(columns, [rows[0]!]);

    // THEN
    const shortOnlyCell = identifierCells()[0]!;

    // With only short content the track must size to that content, not to the cap.
    expect(shortOnlyCell.getBoundingClientRect().width).toBeLessThan(320);
  });

  test("actually truncates the overflowing label", async () => {
    // GIVEN
    await renderTable(columns, rows);

    // THEN
    const link = identifierCells()[1]!.querySelector("a")!;
    const truncatedLabel = link.querySelector("span")!;

    // Before the fix this fails: the cell box grows to fit the text, so `truncate`
    // has nothing to clip and scrollWidth === clientWidth.
    expect(truncatedLabel.scrollWidth).toBeGreaterThan(truncatedLabel.clientWidth);

    // The ellipsis only renders if the clipping happens on a child of the button,
    // since `text-overflow` has no effect on a flex container.
    expect(getComputedStyle(truncatedLabel).textOverflow).toBe("ellipsis");
    expect(getComputedStyle(truncatedLabel).display).toBe("block");

    // And the button itself must stay inside the capped column.
    expect(link.scrollWidth).toBeLessThanOrEqual(link.clientWidth);
  });

  test("renders an ellipsis for a composed label that truncates its own text", async () => {
    // GIVEN a label shaped like the IP prefix column: markers alongside the value,
    // with only the value truncating.
    const composedColumns = buildColumns(() => (
      <span className="flex min-w-0 gap-1">
        <span className="size-1 shrink-0 rounded-full bg-black" />
        <span className="truncate" data-testid="composed-value">
          {LONG_LABEL}
        </span>
      </span>
    ));
    await renderTable(composedColumns, [rows[1]!]);

    // THEN the ellipsis lands on the text, not on an ancestor that would clip the
    // whole row mid-character.
    const value = document.querySelector<HTMLElement>('[data-testid="composed-value"]')!;
    expect(value.scrollWidth).toBeGreaterThan(value.clientWidth);
    expect(getComputedStyle(value).textOverflow).toBe("ellipsis");

    // And the markers keep their width instead of collapsing in the capped column.
    const marker = document.querySelector<HTMLElement>('[data-testid="identifier-cell"] .size-1')!;
    expect(marker.getBoundingClientRect().width).toBeGreaterThan(0);
  });

  test("keeps the sticky footer above the sticky row actions", async () => {
    // GIVEN a table that renders its count footer
    await render(
      <div className="w-[600px] overflow-x-auto">
        <DataTable columns={columns} data={rows} count={rows.length} />
      </div>
    );

    // THEN every footer cell outranks the sticky action cells, so the last row's
    // action menu cannot punch through the count bar.
    const grid = document.querySelector('[style*="grid-template-columns"]')!;
    const footerCells = [...grid.children].filter(
      (el) => getComputedStyle(el).position === "sticky" && getComputedStyle(el).bottom === "0px"
    );
    expect(footerCells.length).toBeGreaterThan(0);

    const actionsZ =
      Number(getComputedStyle(document.querySelector('[data-testid="actions-cell"]')!).zIndex) || 0;
    for (const cell of footerCells) {
      expect(Number(getComputedStyle(cell).zIndex) || 0).toBeGreaterThan(actionsZ);
    }
  });

  test("does not let the first column cover the row action menu", async () => {
    // GIVEN
    await renderTable(columns, rows);

    // THEN
    const identifierRect = identifierCells()[1]!.getBoundingClientRect();
    const actionsRect = document
      .querySelectorAll('[data-testid="actions-cell"]')[1]!
      .getBoundingClientRect();

    expect(identifierRect.right).toBeLessThanOrEqual(actionsRect.left);
  });
});

describe("DataTable first column tooltip", () => {
  test("shows the full value on hover when the label is a string", async () => {
    // GIVEN
    const component = await renderTable(columns, rows);

    // WHEN
    await initPointerTracking(component.locator);
    await component.getByRole("link", { name: LONG_LABEL }).hover();

    // THEN
    await expect.element(component.getByRole("tooltip", { name: LONG_LABEL })).toBeVisible();
  });

  test("renders no tooltip when the label is not a plain string", async () => {
    // GIVEN
    const nodeLabelColumns = buildColumns(() => <span>{LONG_LABEL}</span>);
    const component = await renderTable(nodeLabelColumns, [rows[1]!]);

    // WHEN
    await initPointerTracking(component.locator);
    await component.getByRole("link", { name: LONG_LABEL }).hover();

    // THEN — the tooltip opens after a 200ms delay, so wait past it before asserting
    // absence rather than racing it.
    await new Promise((resolve) => setTimeout(resolve, 600));
    expect(component.getByRole("tooltip").query()).toBeNull();
  });

  test("shows the tooltip for a composed label when one is named explicitly", async () => {
    // GIVEN a label built from markup rather than a plain string
    const nodeLabelColumns = buildColumns(() => <span>{LONG_LABEL}</span>, LONG_LABEL);
    const component = await renderTable(nodeLabelColumns, [rows[1]!]);

    // WHEN
    await initPointerTracking(component.locator);
    await component.getByRole("link", { name: LONG_LABEL }).hover();

    // THEN
    await expect.element(component.getByRole("tooltip", { name: LONG_LABEL })).toBeVisible();
  });
});

interface VisibilityRow {
  id: string;
  name: string;
  __typename: string;
}

const visibilityColumnHelper = createColumnHelper<VisibilityRow>();

// Mirrors the real object table's shape: an identity column, one schema field
// column, the kind column and the actions column.
const visibilityColumns: Array<ColumnDef<VisibilityRow, unknown>> = [
  visibilityColumnHelper.display({
    id: "id",
    header: () => <div>Identifier</div>,
    cell: ({ row }) => <div>{row.original.id}</div>,
  }),
  visibilityColumnHelper.display({
    id: "name",
    header: () => <div>Device name</div>,
    cell: ({ row }) => <div>{row.original.name}</div>,
  }),
  visibilityColumnHelper.display({
    id: "objectKind",
    header: () => <div>Kind</div>,
    cell: ({ row }) => <div>{row.original.__typename}</div>,
  }),
  visibilityColumnHelper.display({
    id: "actions",
    header: () => <div>Actions</div>,
    cell: () => <div>Edit</div>,
  }),
];

const visibilityRows: Array<VisibilityRow> = [
  { id: "device-1", name: "atl1-core1", __typename: "InfraDevice" },
];

describe("DataTable column visibility", () => {
  test("renders a header for every column when no visibility state is given", async () => {
    // GIVEN
    const columnVisibility = undefined;

    // WHEN
    const component = await render(
      <DataTable
        columns={visibilityColumns}
        data={visibilityRows}
        columnVisibility={columnVisibility}
      />
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
      <DataTable
        columns={visibilityColumns}
        data={visibilityRows}
        columnVisibility={columnVisibility}
      />
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
      <DataTable
        columns={visibilityColumns}
        data={visibilityRows}
        columnVisibility={columnVisibility}
      />
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
        columns={visibilityColumns}
        data={visibilityRows}
        columnVisibility={columnVisibility}
        role="grid"
        aria-label="Devices"
      />
    );

    // THEN
    const grid = component.getByRole("grid", { name: "Devices" }).element();
    // 3 of the 4 columns are visible, so the default formula must lay out 3 tracks — one per
    // rendered cell. A 4th (phantom) track misaligns every row. The track function is read from
    // the same constant the component uses, so capping long columns can change without breaking
    // this assertion about the track *count*.
    expect(grid.style.gridTemplateColumns).toBe(
      `repeat(1, fit-content(${COLUMN_MAX_WIDTH})) 1fr 2.5rem`
    );
  });

  test("lays out a two-track grid when every field column is hidden", async () => {
    // GIVEN only the identity and actions columns are left, as on a node schema
    // (no `objectKind` column) with every field column hidden.
    const columnVisibility = { name: false, objectKind: false };

    // WHEN
    const component = await render(
      <DataTable
        columns={visibilityColumns}
        data={visibilityRows}
        columnVisibility={columnVisibility}
        role="grid"
        aria-label="Devices"
      />
    );

    // THEN the formula must skip `repeat()` entirely: `repeat(0, …)` is invalid CSS, so the CSSOM
    // would reject the whole declaration and leave an empty inline style.
    const grid = component.getByRole("grid", { name: "Devices" }).element();
    expect(grid.style.gridTemplateColumns).toBe("1fr 2.5rem");

    // …and with a declaration the grid actually accepts, the two remaining body cells stay on one
    // row. A rejected declaration collapses the grid to a single implicit column, which pushes the
    // actions cell onto a row of its own and doubles the height of every row in the table.
    const identityCell = component.getByText("device-1").element();
    const actionsCell = component.getByText("Edit").element();
    expect(identityCell.getBoundingClientRect().top).toBe(actionsCell.getBoundingClientRect().top);
  });

  test("keeps the identity column when every other column is hidden", async () => {
    // GIVEN
    const columnVisibility = { name: false, objectKind: false, actions: false };

    // WHEN
    const component = await render(
      <DataTable
        columns={visibilityColumns}
        data={visibilityRows}
        columnVisibility={columnVisibility}
      />
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
        columns={visibilityColumns}
        data={visibilityRows}
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
