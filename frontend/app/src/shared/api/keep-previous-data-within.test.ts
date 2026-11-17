import { describe, expect, it } from "vitest";

import { keepPreviousDataWithin } from "./keep-previous-data-within";

interface Page {
  rows: string[];
}

const LIST_KEY = ["repository", "branch", { branchName: "feature" }];
const PAGE_KEY = [...LIST_KEY, { offset: 10 }];

describe("keepPreviousDataWithin", () => {
  it("keeps the previous page of the same list", () => {
    // GIVEN
    const previous: Page = { rows: ["a"] };

    // WHEN
    const placeholder = keepPreviousDataWithin<Page>(LIST_KEY)(previous, { queryKey: PAGE_KEY });

    // THEN
    expect(placeholder).toBe(previous);
  });

  it("drops the previous page of another list", () => {
    // WHEN
    const placeholder = keepPreviousDataWithin<Page>(LIST_KEY)(
      { rows: ["a"] },
      { queryKey: ["repository", "branch", { branchName: "other" }] }
    );

    // THEN
    expect(placeholder).toBeUndefined();
  });

  it("drops a previous page without rows when the list says how to count them", () => {
    // WHEN
    const placeholder = keepPreviousDataWithin<Page>(LIST_KEY, (page) => page.rows.length > 0)(
      { rows: [] },
      { queryKey: PAGE_KEY }
    );

    // THEN
    expect(placeholder).toBeUndefined();
  });

  it("keeps a previous page with rows when the list says how to count them", () => {
    // GIVEN
    const previous: Page = { rows: ["a"] };

    // WHEN
    const placeholder = keepPreviousDataWithin<Page>(LIST_KEY, (page) => page.rows.length > 0)(
      previous,
      { queryKey: PAGE_KEY }
    );

    // THEN
    expect(placeholder).toBe(previous);
  });
});
