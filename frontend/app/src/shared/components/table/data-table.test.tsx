import type { ColumnDef } from "@tanstack/react-table";
import { describe, expect, test } from "vitest";

import { DataTable } from "@/shared/components/table/data-table";

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

const buildColumns = (label: (row: DemoRow) => React.ReactNode): ColumnDef<DemoRow>[] => [
  {
    id: "identifier",
    header: () => <StickyLeftCell>Name</StickyLeftCell>,
    cell: ({ row }) => (
      <TableIdentifierCell
        objectKind="TestingOverflowDemo"
        objectId={row.original.id}
        label={label(row.original)}
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
});
