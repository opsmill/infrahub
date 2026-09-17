import { describe, expect, it } from "vitest";

import { PAGE_SIZE } from "@/shared/utils/table-pagination";

import { render } from "../../../tests/components/render";
import { useTablePagination } from "./use-table-pagination";

const Probe = ({ urlKey }: { urlKey: string }) => {
  const { page, pageSize, offset, setPage } = useTablePagination({ urlKey });

  return (
    <section aria-label={urlKey}>
      <p>{`page ${page}`}</p>
      <p>{`size ${pageSize}`}</p>
      <p>{`offset ${offset}`}</p>

      <button
        onClick={() => {
          setPage(page + 1);
        }}
        type="button"
      >
        Next
      </button>
    </section>
  );
};

describe("useTablePagination", () => {
  it("starts on the first page at the fixed size", async () => {
    // GIVEN
    const urlKey = "branches";

    // WHEN
    const component = await render(<Probe urlKey={urlKey} />);

    // THEN
    await expect.element(component.getByText("page 1")).toBeVisible();
    await expect.element(component.getByText(`size ${PAGE_SIZE}`)).toBeVisible();
    await expect.element(component.getByText("offset 0")).toBeVisible();
  });

  it("derives the offset from the page it moves to", async () => {
    // GIVEN
    const component = await render(<Probe urlKey="branches" />);

    // WHEN
    await component.getByRole("button", { name: "Next" }).click();

    // THEN
    await expect.element(component.getByText("page 2")).toBeVisible();
    await expect.element(component.getByText(`offset ${PAGE_SIZE}`)).toBeVisible();
  });

  it("carries the page in the url under its own key", async () => {
    // GIVEN
    const component = await render(<Probe urlKey="branches" />);

    // WHEN
    await component.getByRole("button", { name: "Next" }).click();

    // THEN
    await expect.poll(() => window.location.search).toContain("branches_page=2");
  });

  it("reads the page it was given in the url", async () => {
    // GIVEN
    window.history.replaceState(null, "", `${window.location.pathname}?branches_page=3`);

    // WHEN
    const component = await render(<Probe urlKey="branches" />);

    // THEN
    await expect.element(component.getByText("page 3")).toBeVisible();
    await expect.element(component.getByText(`offset ${PAGE_SIZE * 2}`)).toBeVisible();
  });

  it("falls back to the first page when the url carries a page below one", async () => {
    // GIVEN
    window.history.replaceState(null, "", `${window.location.pathname}?branches_page=0`);

    // WHEN
    const component = await render(<Probe urlKey="branches" />);

    // THEN
    await expect.element(component.getByText("page 1")).toBeVisible();
    await expect.element(component.getByText("offset 0")).toBeVisible();
  });

  it("falls back to the first page when the url carries a page that is not a number", async () => {
    // GIVEN
    window.history.replaceState(null, "", `${window.location.pathname}?branches_page=not-a-page`);

    // WHEN
    const component = await render(<Probe urlKey="branches" />);

    // THEN
    await expect.element(component.getByText("page 1")).toBeVisible();
    await expect.element(component.getByText("offset 0")).toBeVisible();
  });

  it("keeps the page size out of the url", async () => {
    // GIVEN
    const component = await render(<Probe urlKey="branches" />);

    // WHEN
    await component.getByRole("button", { name: "Next" }).click();

    // THEN
    await expect.poll(() => window.location.search).toContain("branches_page=2");
    expect(window.location.search).not.toContain("branches_size");
  });

  it("leaves a table under a different url key where it was", async () => {
    // GIVEN
    const component = await render(
      <>
        <Probe urlKey="branches" />
        <Probe urlKey="artifacts" />
      </>
    );
    const branches = component.getByRole("region", { name: "branches" });
    const artifacts = component.getByRole("region", { name: "artifacts" });

    // WHEN
    await branches.getByRole("button", { name: "Next" }).click();

    // THEN
    await expect.element(branches.getByText("page 2")).toBeVisible();
    await expect.element(artifacts.getByText("page 1")).toBeVisible();
  });
});
