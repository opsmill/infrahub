import { Card, CardContent, CardHeader } from "@infrahub/ui";
import { useState } from "react";
import { describe, expect, test } from "vitest";

import { DEFAULT_PAGE_SIZE, getPageWindow } from "@/shared/utils/table-pagination";

import { render } from "../../../../tests/components/render";
import { TablePagination } from "./table-pagination";

interface PagedCardProps {
  totalCount: number;
  initialPage?: number;
}

const PagedCard = ({ totalCount, initialPage = 1 }: PagedCardProps) => {
  const [page, setPage] = useState(initialPage);
  const [pageSize, setPageSize] = useState<number>(DEFAULT_PAGE_SIZE);
  const { firstRow, lastRow } = getPageWindow(page, pageSize, totalCount);
  const rows = Array.from({ length: Math.max(lastRow - firstRow + 1, 0) }, (_, index) => (
    <li key={firstRow + index}>{`Branch ${firstRow + index}`}</li>
  ));

  return (
    <Card className="h-64 overflow-hidden">
      <CardHeader>Branches</CardHeader>

      <CardContent className="min-h-0 flex-1 overflow-auto">
        <ul>{rows}</ul>
      </CardContent>

      <TablePagination
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
        page={page}
        pageSize={pageSize}
        totalCount={totalCount}
      />
    </Card>
  );
};

describe("TablePagination", () => {
  test("states the window and the total", async () => {
    // GIVEN
    const totalCount = 45;

    // WHEN
    const component = await render(<PagedCard totalCount={totalCount} />);

    // THEN
    await expect.element(component.getByText("Showing 1 to 20 of 45")).toBeVisible();
  });

  test("marks the page being shown as the current one", async () => {
    // GIVEN
    const totalCount = 45;

    // WHEN
    const component = await render(<PagedCard totalCount={totalCount} />);

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Page 1" }))
      .toHaveAttribute("aria-current", "page");
    await expect
      .element(component.getByRole("button", { name: "Page 2" }))
      .not.toHaveAttribute("aria-current");
  });

  test("shows the next page of rows from inside a fixed-height card", async () => {
    // GIVEN
    const component = await render(<PagedCard totalCount={45} />);

    // WHEN
    await component.getByRole("button", { name: "Next page" }).click();

    // THEN
    await expect.element(component.getByText("Branch 21", { exact: true })).toBeVisible();
    await expect.element(component.getByText("Branch 1", { exact: true })).not.toBeInTheDocument();
  });

  test("announces the window it moved to", async () => {
    // GIVEN
    const component = await render(<PagedCard totalCount={45} />);

    // WHEN
    await component.getByRole("button", { name: "Next page" }).click();

    // THEN
    await expect.element(component.getByRole("status")).toHaveTextContent("Showing 21 to 40 of 45");
  });

  test("goes back to the previous page", async () => {
    // GIVEN
    const component = await render(<PagedCard initialPage={2} totalCount={45} />);

    // WHEN
    await component.getByRole("button", { name: "Previous page" }).click();

    // THEN
    await expect.element(component.getByText("Branch 1", { exact: true })).toBeVisible();
    await expect.element(component.getByText("Showing 1 to 20 of 45")).toBeVisible();
  });

  test("jumps to a page chosen directly", async () => {
    // GIVEN
    const component = await render(<PagedCard totalCount={45} />);

    // WHEN
    await component.getByRole("button", { name: "Page 3" }).click();

    // THEN
    await expect.element(component.getByText("Branch 41", { exact: true })).toBeVisible();
    await expect.element(component.getByText("Showing 41 to 45 of 45")).toBeVisible();
  });

  test("cannot leave the first page backwards", async () => {
    // GIVEN
    const totalCount = 45;

    // WHEN
    const component = await render(<PagedCard totalCount={totalCount} />);

    // THEN
    await expect.element(component.getByRole("button", { name: "Previous page" })).toBeDisabled();
  });

  test("cannot leave the last page forwards", async () => {
    // GIVEN
    const totalCount = 45;

    // WHEN
    const component = await render(<PagedCard initialPage={3} totalCount={totalCount} />);

    // THEN
    await expect.element(component.getByRole("button", { name: "Next page" })).toBeDisabled();
  });

  test("resizes the page from the labelled page-size selector", async () => {
    // GIVEN
    const component = await render(<PagedCard totalCount={45} />);

    // WHEN
    await component.getByRole("button", { name: /Rows per page/ }).click();
    await component.getByRole("option", { name: "50" }).click();

    // THEN
    await expect.element(component.getByText("Showing 1 to 45 of 45")).toBeVisible();
    await expect.element(component.getByText("Branch 45", { exact: true })).toBeVisible();
  });

  test("states an empty set without offering a second page", async () => {
    // GIVEN
    const totalCount = 0;

    // WHEN
    const component = await render(<PagedCard totalCount={totalCount} />);

    // THEN
    await expect.element(component.getByText("Showing 0 of 0")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Page 2" })).not.toBeInTheDocument();
  });
});
