import { queryOptions } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { render } from "../../../tests/components/render";
import { useCountClampedQuery } from "./use-count-clamped-query";

const PAGE_SIZE = 10;
let total = 25;

const fetchPage = vi.fn(async (offset: number) => ({
  rows: Array.from({ length: Math.max(Math.min(PAGE_SIZE, total - offset), 0) }, (_, index) =>
    String(offset + index + 1)
  ),
  count: total,
}));

const renders: string[] = [];

interface ProbeProps {
  list?: string;
  page: number;
  refetchInterval?: number;
}

const Probe = ({ list = "a", page, refetchInterval }: ProbeProps) => {
  const { page: currentPage, query } = useCountClampedQuery(
    { page, pageSize: PAGE_SIZE },
    (offset) =>
      queryOptions({
        queryKey: ["probe", { list, offset }],
        queryFn: () => fetchPage(offset),
        refetchInterval,
        // Keeps the previous page on screen while the next one loads, within one list only.
        placeholderData: (previousData, previousQuery) => {
          const previousParams: unknown = previousQuery?.queryKey.at(-1);
          const isSameList =
            typeof previousParams === "object" &&
            previousParams !== null &&
            "list" in previousParams &&
            previousParams.list === list;

          return isSameList ? previousData : undefined;
        },
      })
  );
  renders.push(
    `page ${currentPage}: ${query.data ? `rows ${query.data.rows.join(",")}` : "loading"}`
  );

  return (
    <section>
      <p>{`page ${currentPage}`}</p>
      <p>{query.data ? `rows ${query.data.rows.join(",")}` : "loading"}</p>
    </section>
  );
};

describe("useCountClampedQuery", () => {
  beforeEach(() => {
    total = 25;
    renders.length = 0;
  });

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

  it("shows the requested page again once the clamped page reports that the row set has grown", async () => {
    // GIVEN
    const component = await render(<Probe page={4} refetchInterval={20} />);
    await expect.element(component.getByText("page 3")).toBeVisible();

    // WHEN
    total = 45;

    // THEN
    await expect.element(component.getByText("page 4")).toBeVisible();
    await expect.element(component.getByText("rows 31,32,33,34,35,36,37,38,39,40")).toBeVisible();
  });

  it("never shows the page past the end as the last real page while it loads", async () => {
    // WHEN
    const component = await render(<Probe page={9} />);

    // THEN
    await expect.element(component.getByText("rows 21,22,23,24,25")).toBeVisible();
    expect(renders).not.toContain("page 3: rows ");
  });

  it("moves to the new last page once the clamped page reports that the row set has shrunk", async () => {
    // GIVEN
    const component = await render(<Probe page={9} refetchInterval={20} />);
    await expect.element(component.getByText("page 3")).toBeVisible();

    // WHEN
    total = 15;

    // THEN
    await expect.element(component.getByText("page 2")).toBeVisible();
    await expect.element(component.getByText("rows 11,12,13,14,15")).toBeVisible();
  });

  it("keeps the clamped page on screen, not an empty page, while the page picked from it loads", async () => {
    // GIVEN
    const component = await render(<Probe page={9} />);
    await expect.element(component.getByText("rows 21,22,23,24,25")).toBeVisible();
    renders.length = 0;

    // WHEN
    await component.rerender(<Probe page={2} />);

    // THEN
    await expect.element(component.getByText("rows 11,12,13,14,15,16,17,18,19,20")).toBeVisible();
    expect(renders).not.toContain("page 2: rows ");
  });

  it("keeps the clamped page until the requested page's own answer shows it back in range", async () => {
    // GIVEN
    const component = await render(<Probe page={4} refetchInterval={20} />);
    await expect.element(component.getByText("rows 21,22,23,24,25")).toBeVisible();

    // WHEN
    total = 45;

    // THEN
    await expect.element(component.getByText("rows 31,32,33,34,35,36,37,38,39,40")).toBeVisible();
    expect(renders).not.toContain("page 4: rows ");
  });

  it("does not clamp another list with the count of the list before it", async () => {
    // GIVEN
    const component = await render(<Probe list="a" page={9} />);
    await expect.element(component.getByText("rows 21,22,23,24,25")).toBeVisible();
    total = 95;
    renders.length = 0;

    // WHEN
    await component.rerender(<Probe list="b" page={9} />);

    // THEN
    await expect.element(component.getByText("rows 81,82,83,84,85,86,87,88,89,90")).toBeVisible();
    expect(renders.filter((entry) => !entry.startsWith("page 9"))).toEqual([]);
  });

  it("moves to the new last page once the requested page reports that the row set has shrunk", async () => {
    // GIVEN
    const offsets = () => fetchPage.mock.calls.map(([offset]) => offset);
    const component = await render(<Probe page={3} refetchInterval={20} />);
    await expect.element(component.getByText("rows 21,22,23,24,25")).toBeVisible();

    // WHEN
    total = 15;

    // THEN
    await expect.element(component.getByText("rows 11,12,13,14,15")).toBeVisible();
    await expect.element(component.getByText("page 2")).toBeVisible();
    expect(renders).not.toContain("page 3: rows ");
    fetchPage.mockClear();
    await expect.poll(() => offsets().filter((offset) => offset === 10).length).toBeGreaterThan(2);
    expect(offsets().filter((offset) => offset === 20)).toEqual([]);
  });
});
