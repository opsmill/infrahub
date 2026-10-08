import { describe, expect, it, vi } from "vitest";

import { render } from "../../../../tests/components/render";
import { PagedTableCard, type PagedTableCardProps } from "./paged-table-card";

interface Page {
  count: number;
  rows: string[];
}

class DeniedError extends Error {}

const renderShell = async (overrides: Partial<PagedTableCardProps<Page>> = {}) => {
  const props: PagedTableCardProps<Page> = {
    title: "Widgets",
    itemName: { one: "widget", other: "widgets" },
    query: {
      data: { count: 2, rows: ["first", "second"] },
      error: null,
      isPlaceholderData: false,
      refetch: vi.fn(),
    },
    page: 1,
    pageSize: 10,
    onPageChange: vi.fn(),
    isDenied: (error) => error instanceof DeniedError,
    deniedMessage: "You can't view these widgets.",
    failedMessage: "Widgets couldn't be loaded.",
    emptyTitle: "No widgets",
    emptyMessage: "Widgets will show here.",
    renderTable: (page) => (
      <ul>
        {page.rows.map((row) => (
          <li key={row}>{row}</li>
        ))}
      </ul>
    ),
    tableTestId: "widgets-table",
    footer: <p>Widget footer</p>,
    ...overrides,
  };

  const component = await render(<PagedTableCard {...props} />);
  return { props, component };
};

const failedQuery = (error: Error) => ({
  data: undefined,
  error,
  isPlaceholderData: false,
  refetch: vi.fn(),
});

describe("PagedTableCard", () => {
  it("keeps the previous rows, not the out-of-range state, while a placeholder is shown", async () => {
    // GIVEN the previous page's rows stand in while page 3 loads
    const { component } = await renderShell({
      page: 3,
      query: {
        data: { count: 2, rows: ["first", "second"] },
        error: null,
        isPlaceholderData: true,
        refetch: vi.fn(),
      },
    });

    // THEN
    await expect.element(component.getByText("first")).toBeVisible();
    expect(component.getByText("Page 3 doesn't exist.").query()).toBeNull();
  });

  it("names its region after the title", async () => {
    // WHEN
    const { component } = await renderShell();

    // THEN
    await expect.element(component.getByRole("region", { name: "Widgets" })).toBeVisible();
  });

  it("shows the formatted count with its noun for screen readers", async () => {
    // WHEN
    const { component } = await renderShell({
      query: {
        data: { count: 1234, rows: ["first"] },
        error: null,
        isPlaceholderData: false,
        refetch: vi.fn(),
      },
    });

    // THEN
    await expect.element(component.getByText("1,234 widgets", { exact: true })).toBeVisible();
  });

  it("uses the singular noun for one row", async () => {
    // WHEN
    const { component } = await renderShell({
      query: {
        data: { count: 1, rows: ["first"] },
        error: null,
        isPlaceholderData: false,
        refetch: vi.fn(),
      },
    });

    // THEN
    await expect.element(component.getByText("1 widget", { exact: true })).toBeVisible();
  });

  it("renders the table and the footer once rows arrive", async () => {
    // WHEN
    const { component } = await renderShell();

    // THEN
    await expect.element(component.getByTestId("widgets-table")).toHaveTextContent("first");
    await expect.element(component.getByText("Widget footer")).toBeVisible();
  });

  it("shows loading rows and no count before the first page arrives", async () => {
    // WHEN
    const { component } = await renderShell({
      query: { data: undefined, error: null, isPlaceholderData: false, refetch: vi.fn() },
    });

    // THEN
    const status = component.getByRole("status");
    await expect.element(status).toHaveAttribute("aria-busy", "true");
    await expect.element(status).toHaveTextContent("Loading widgets");
    expect(component.getByText(/^\d+ widgets?$/).query()).toBeNull();
    expect(component.getByText("Widget footer").query()).toBeNull();
  });

  it("shows the denied message when the error is a denial", async () => {
    // WHEN
    const { component } = await renderShell({ query: failedQuery(new DeniedError("denied")) });

    // THEN
    await expect.element(component.getByText("You can't view these widgets.")).toBeVisible();
    expect(component.getByRole("alert").query()).toBeNull();
  });

  it("offers to try again when the first page fails", async () => {
    // GIVEN
    const query = failedQuery(new Error("broken"));
    const { component } = await renderShell({ query });
    await expect
      .element(component.getByRole("alert"))
      .toHaveTextContent("Widgets couldn't be loaded.");

    // WHEN
    await component.getByRole("button", { name: "Try again" }).click();

    // THEN
    expect(query.refetch).toHaveBeenCalledOnce();
  });

  it("offers the first page when a later page fails", async () => {
    // GIVEN
    const { props, component } = await renderShell({
      query: failedQuery(new Error("broken")),
      page: 3,
    });

    // WHEN
    await component.getByRole("button", { name: "Go to first page" }).click();

    // THEN
    expect(props.onPageChange).toHaveBeenCalledWith(1);
  });

  it("shows the empty title and message, and no footer, when the list is empty", async () => {
    // WHEN
    const { component } = await renderShell({
      query: {
        data: { count: 0, rows: [] },
        error: null,
        isPlaceholderData: false,
        refetch: vi.fn(),
      },
    });

    // THEN
    await expect.element(component.getByText("No widgets")).toBeVisible();
    await expect.element(component.getByText("Widgets will show here.")).toBeVisible();
    expect(component.getByText("Widget footer").query()).toBeNull();
  });

  it("says a page past the end doesn't exist and goes to the last page on request", async () => {
    // GIVEN
    const { props, component } = await renderShell({
      query: {
        data: { count: 25, rows: [] },
        error: null,
        isPlaceholderData: false,
        refetch: vi.fn(),
      },
      page: 9,
    });
    await expect.element(component.getByText("Page 9 doesn't exist.")).toBeVisible();

    // WHEN
    await component.getByRole("button", { name: "Go to last page" }).click();

    // THEN
    expect(props.onPageChange).toHaveBeenCalledWith(3);
  });

  it("keeps a full page's height and shows the pager when the list has several pages", async () => {
    // WHEN
    const { component } = await renderShell({
      query: {
        data: { count: 25, rows: ["first"] },
        error: null,
        isPlaceholderData: false,
        refetch: vi.fn(),
      },
      page: 3,
    });

    // THEN
    await expect.element(component.getByTestId("widgets-table")).toHaveClass("min-h-110");
    await expect
      .element(component.getByRole("navigation", { name: "Widgets pagination" }))
      .toBeVisible();
  });

  it("lets a single page take only the height of its rows", async () => {
    // WHEN
    const { component } = await renderShell();

    // THEN
    await expect.element(component.getByTestId("widgets-table")).not.toHaveClass("min-h-110");
    expect(component.getByRole("navigation").query()).toBeNull();
  });
});
