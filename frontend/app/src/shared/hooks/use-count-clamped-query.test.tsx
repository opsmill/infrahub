import { queryOptions } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { render } from "../../../tests/components/render";
import { useCountClampedQuery } from "./use-count-clamped-query";

const TOTAL = 25;
const PAGE_SIZE = 10;

const fetchPage = vi.fn(async (offset: number) => ({
  rows: Array.from({ length: Math.max(Math.min(PAGE_SIZE, TOTAL - offset), 0) }, (_, index) =>
    String(offset + index + 1)
  ),
  count: TOTAL,
}));

const Probe = ({ page, refetchInterval }: { page: number; refetchInterval?: number }) => {
  const { page: currentPage, query } = useCountClampedQuery(
    { page, pageSize: PAGE_SIZE },
    (offset) =>
      queryOptions({
        queryKey: ["probe", offset],
        queryFn: () => fetchPage(offset),
        refetchInterval,
      })
  );

  return (
    <section>
      <p>{`page ${currentPage}`}</p>
      <p>{query.data ? `rows ${query.data.rows.join(",")}` : "loading"}</p>
    </section>
  );
};

describe("useCountClampedQuery", () => {
  it("shows the requested page when it is in range", async () => {
    // WHEN
    const component = await render(<Probe page={2} />);

    // THEN
    await expect.element(component.getByText("rows 11,12,13,14,15,16,17,18,19,20")).toBeVisible();
    await expect.element(component.getByText("page 2")).toBeVisible();
  });

  it("asks for the last real page once the count shows the requested one is past the end", async () => {
    // GIVEN
    fetchPage.mockClear();

    // WHEN
    const component = await render(<Probe page={9} />);

    // THEN
    await expect.element(component.getByText("rows 21,22,23,24,25")).toBeVisible();
    await expect.element(component.getByText("page 3")).toBeVisible();
    expect(fetchPage.mock.calls.map(([offset]) => offset)).toEqual([80, 20]);
  });

  it("stops polling the page past the end once it has clamped", async () => {
    // GIVEN
    fetchPage.mockClear();
    const offsets = () => fetchPage.mock.calls.map(([offset]) => offset);

    // WHEN
    const component = await render(<Probe page={9} refetchInterval={20} />);
    await expect.element(component.getByText("page 3")).toBeVisible();
    await expect.poll(() => offsets().filter((offset) => offset === 20).length).toBeGreaterThan(2);

    // THEN
    expect(offsets().filter((offset) => offset === 80)).toHaveLength(1);
  });
});
