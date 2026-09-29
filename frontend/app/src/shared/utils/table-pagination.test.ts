import { describe, expect, it } from "vitest";

import {
  clampPage,
  formatPageWindow,
  getPageItems,
  getTotalPages,
  TABLE_PAGE_SIZE,
  TABLE_ROW_HEIGHT_PX,
} from "./table-pagination";

describe("table pagination constants", () => {
  it("uses 10 rows of 40px", () => {
    expect(TABLE_PAGE_SIZE).toBe(10);
    expect(TABLE_ROW_HEIGHT_PX).toBe(40);
  });
});

describe("getTotalPages", () => {
  it.each([
    [0, 1],
    [10, 1],
    [11, 2],
    [40, 4],
    [-5, 1],
  ])("returns the page count for %i rows", (totalCount, expected) => {
    expect(getTotalPages(totalCount, TABLE_PAGE_SIZE)).toBe(expected);
  });
});

describe("clampPage", () => {
  it.each([
    [0, 1],
    [-3, 1],
    [Number.NaN, 1],
    [Number.POSITIVE_INFINITY, 1],
    [2.7, 2],
    [3, 3],
    [9, 4],
  ])("clamps page %d to %i of 4 pages", (page, expected) => {
    expect(clampPage(page, 4)).toBe(expected);
  });

  it("returns 1 when there is a single page", () => {
    expect(clampPage(5, 1)).toBe(1);
  });
});

describe("getPageItems", () => {
  it("lists every page when they all fit", () => {
    expect(getPageItems(1, 3)).toEqual([1, 2, 3]);
  });

  it("returns a single page for a single-page table", () => {
    expect(getPageItems(1, 1)).toEqual([1]);
  });

  it("shows a trailing ellipsis on the first page", () => {
    expect(getPageItems(1, 10)).toEqual([1, 2, "ellipsis", 10]);
  });

  it("shows ellipses on both sides on a middle page", () => {
    expect(getPageItems(5, 10)).toEqual([1, "ellipsis", 4, 5, 6, "ellipsis", 10]);
  });

  it("shows a leading ellipsis on the last page", () => {
    expect(getPageItems(10, 10)).toEqual([1, "ellipsis", 9, 10]);
  });

  it("does not use an ellipsis to hide a single page", () => {
    expect(getPageItems(3, 5)).toEqual([1, 2, 3, 4, 5]);
  });

  it("clamps a page past the end", () => {
    expect(getPageItems(99, 4)).toEqual([1, "ellipsis", 3, 4]);
  });
});

describe("formatPageWindow", () => {
  it("shows the row range of the current page", () => {
    expect(formatPageWindow(1, TABLE_PAGE_SIZE, 40)).toBe("Showing 1 to 10 of 40");
    expect(formatPageWindow(4, TABLE_PAGE_SIZE, 40)).toBe("Showing 31 to 40 of 40");
  });

  it("shows a single row when the first and last rows are the same", () => {
    expect(formatPageWindow(2, TABLE_PAGE_SIZE, 11)).toBe("Showing 11 of 11");
  });

  it("shows zero rows for an empty table", () => {
    expect(formatPageWindow(1, TABLE_PAGE_SIZE, 0)).toBe("Showing 0 of 0");
  });

  it("clamps an out-of-range page", () => {
    expect(formatPageWindow(9, TABLE_PAGE_SIZE, 11)).toBe("Showing 11 of 11");
    expect(formatPageWindow(Number.NaN, TABLE_PAGE_SIZE, 10)).toBe("Showing 1 to 10 of 10");
  });

  it("formats large numbers", () => {
    expect(formatPageWindow(1, TABLE_PAGE_SIZE, 1200)).toBe("Showing 1 to 10 of 1,200");
  });
});
