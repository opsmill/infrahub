import { describe, expect, test } from "vitest";

import {
  clampPage,
  DEFAULT_PAGE_SIZE,
  formatPageWindow,
  getOffset,
  getPageFromOffset,
  getPageItems,
  getPageWindow,
  getTotalPages,
  isPageSize,
  PAGE_SIZE_OPTIONS,
  toPageNumber,
} from "./table-pagination";

describe("page sizes", () => {
  test("offers 10, 20 and 50", () => {
    expect(PAGE_SIZE_OPTIONS).toEqual([10, 20, 50]);
  });

  test("defaults to 10", () => {
    expect(DEFAULT_PAGE_SIZE).toBe(10);
  });

  test("accepts an offered size", () => {
    expect(isPageSize(50)).toBe(true);
  });

  test("rejects a size that is not offered", () => {
    expect(isPageSize(25)).toBe(false);
  });
});

describe("toPageNumber", () => {
  test("keeps a page within range", () => {
    expect(toPageNumber(3)).toBe(3);
  });

  test("raises a page below one", () => {
    expect(toPageNumber(0)).toBe(1);
    expect(toPageNumber(-4)).toBe(1);
  });

  test("falls back to the first page for a non-finite value", () => {
    expect(toPageNumber(Number.NaN)).toBe(1);
  });
});

describe("getTotalPages", () => {
  test("counts a partial last page", () => {
    expect(getTotalPages(45, 20)).toBe(3);
  });

  test("counts an exact multiple of the page size", () => {
    expect(getTotalPages(40, 20)).toBe(2);
  });

  test("counts a set smaller than one page as one page", () => {
    expect(getTotalPages(7, 20)).toBe(1);
  });

  test("counts an empty set as one page", () => {
    expect(getTotalPages(0, 20)).toBe(1);
  });
});

describe("clampPage", () => {
  test("keeps a page inside the range", () => {
    expect(clampPage(2, 3)).toBe(2);
  });

  test("clamps past the last page", () => {
    expect(clampPage(9, 3)).toBe(3);
  });

  test("clamps before the first page", () => {
    expect(clampPage(0, 3)).toBe(1);
  });
});

describe("page and offset conversion", () => {
  test("the first page starts at offset zero", () => {
    expect(getOffset(1, 20)).toBe(0);
  });

  test("the last page starts after every preceding page", () => {
    expect(getOffset(3, 20)).toBe(40);
  });

  test("an offset resolves back to its page", () => {
    expect(getPageFromOffset(40, 20)).toBe(3);
  });

  test("a zero offset resolves to the first page", () => {
    expect(getPageFromOffset(0, 20)).toBe(1);
  });
});

describe("getPageWindow", () => {
  test("describes the first page of a larger set", () => {
    expect(getPageWindow(1, 20, 45)).toEqual({ firstRow: 1, lastRow: 20, totalCount: 45 });
  });

  test("describes a partial last page", () => {
    expect(getPageWindow(3, 20, 45)).toEqual({ firstRow: 41, lastRow: 45, totalCount: 45 });
  });

  test("describes a last page that is an exact multiple of the page size", () => {
    expect(getPageWindow(2, 20, 40)).toEqual({ firstRow: 21, lastRow: 40, totalCount: 40 });
  });

  test("describes a set smaller than one page", () => {
    expect(getPageWindow(1, 20, 7)).toEqual({ firstRow: 1, lastRow: 7, totalCount: 7 });
  });

  test("describes an empty set", () => {
    expect(getPageWindow(1, 20, 0)).toEqual({ firstRow: 0, lastRow: 0, totalCount: 0 });
  });

  test("describes the last page when asked for a page past the end", () => {
    expect(getPageWindow(8, 20, 45)).toEqual({ firstRow: 41, lastRow: 45, totalCount: 45 });
  });
});

describe("formatPageWindow", () => {
  test("states the window and the total on the first page", () => {
    expect(formatPageWindow(1, 20, 45)).toBe("Showing 1 to 20 of 45");
  });

  test("states the window and the total on the last page", () => {
    expect(formatPageWindow(3, 20, 45)).toBe("Showing 41 to 45 of 45");
  });

  test("states the whole set when it is smaller than one page", () => {
    expect(formatPageWindow(1, 20, 7)).toBe("Showing 1 to 7 of 7");
  });

  test("states a single row without a range", () => {
    expect(formatPageWindow(1, 20, 1)).toBe("Showing 1 of 1");
  });

  test("states an empty set", () => {
    expect(formatPageWindow(1, 20, 0)).toBe("Showing 0 of 0");
  });

  test("groups thousands", () => {
    expect(formatPageWindow(1, 20, 1234)).toBe("Showing 1 to 20 of 1,234");
  });
});

describe("getPageItems", () => {
  test("lists every page when they all fit", () => {
    expect(getPageItems(1, 3)).toEqual([1, 2, 3]);
  });

  test("lists the only page of a single-page set", () => {
    expect(getPageItems(1, 1)).toEqual([1]);
  });

  test("keeps the first and last page reachable from the middle", () => {
    expect(getPageItems(10, 20)).toEqual([1, "ellipsis", 9, 10, 11, "ellipsis", 20]);
  });

  test("elides only the far side on the first page", () => {
    expect(getPageItems(1, 20)).toEqual([1, 2, "ellipsis", 20]);
  });

  test("elides only the near side on the last page", () => {
    expect(getPageItems(20, 20)).toEqual([1, "ellipsis", 19, 20]);
  });
});
