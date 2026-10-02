import { describe, expect, it, vi } from "vitest";

import { TablePagination } from "@/shared/components/table/table-pagination";

import { render } from "../../../../tests/components/render";

describe("TablePagination", () => {
  it("renders the row window of the current page", async () => {
    // WHEN
    const component = await render(
      <TablePagination page={2} pageSize={10} totalCount={35} onPageChange={vi.fn()} />
    );

    // THEN
    await expect.element(component.getByRole("status")).toHaveTextContent("Showing 11 to 20 of 35");
    await expect
      .element(component.getByRole("button", { name: "Page 2" }))
      .toHaveAttribute("aria-current", "page");
    await expect
      .element(component.getByRole("button", { name: "Page 1" }))
      .not.toHaveAttribute("aria-current");
  });

  it("calls onPageChange with the page that was pressed", async () => {
    // GIVEN
    const onPageChange = vi.fn();
    const component = await render(
      <TablePagination page={2} pageSize={10} totalCount={35} onPageChange={onPageChange} />
    );

    // WHEN
    await component.getByRole("button", { name: "Page 4" }).click();
    await component.getByRole("button", { name: "Next page" }).click();
    await component.getByRole("button", { name: "Previous page" }).click();

    // THEN
    expect(onPageChange.mock.calls).toEqual([[4], [3], [1]]);
  });

  it("disables Previous on the first page", async () => {
    // WHEN
    const component = await render(
      <TablePagination page={1} pageSize={10} totalCount={35} onPageChange={vi.fn()} />
    );

    // THEN
    await expect.element(component.getByRole("button", { name: "Previous page" })).toBeDisabled();
    await expect.element(component.getByRole("button", { name: "Next page" })).toBeEnabled();
  });

  it("disables Next on the last page", async () => {
    // WHEN
    const component = await render(
      <TablePagination page={4} pageSize={10} totalCount={35} onPageChange={vi.fn()} />
    );

    // THEN
    await expect.element(component.getByRole("button", { name: "Next page" })).toBeDisabled();
    await expect.element(component.getByRole("button", { name: "Previous page" })).toBeEnabled();
  });

  it("hides ellipses from assistive technology", async () => {
    // WHEN
    const component = await render(
      <TablePagination page={5} pageSize={10} totalCount={100} onPageChange={vi.fn()} />
    );

    // THEN
    const ellipses = component.container.querySelectorAll('span[aria-hidden="true"]');
    expect(ellipses).toHaveLength(2);
    expect(component.getByRole("button", { name: /^Page / }).elements()).toHaveLength(5);
  });

  it("names the landmark after the table it pages", async () => {
    // WHEN
    const component = await render(
      <TablePagination
        page={1}
        pageSize={10}
        totalCount={35}
        onPageChange={vi.fn()}
        aria-label="Tasks pagination"
      />
    );

    // THEN
    await expect
      .element(component.getByRole("navigation", { name: "Tasks pagination", exact: true }))
      .toBeVisible();
  });
});
