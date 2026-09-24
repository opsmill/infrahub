import { describe, expect, it } from "vitest";

import {
  clampPage,
  formatPageWindow,
  getOffset,
  getPageItems,
  getPageWindow,
  getTotalPages,
  PAGE_SIZE,
  toPageNumber,
} from "./table-pagination";

describe("page size", () => {
  it("holds ten rows", () => {
    expect(PAGE_SIZE).toBe(10);
  });
});

describe("toPageNumber", () => {
  it("keeps a page within range", () => {
    expect(toPageNumber(3)).toBe(3);
  });

  it("raises a page below one", () => {
    expect(toPageNumber(0)).toBe(1);
    expect(toPageNumber(-4)).toBe(1);
  });

  it("falls back to the first page for a non-finite value", () => {
    expect(toPageNumber(Number.NaN)).toBe(1);
  });
});

describe("getTotalPages", () => {
  it("counts a partial last page", () => {
    expect(getTotalPages(45, 20)).toBe(3);
  });

  it("counts an exact multiple of the page size", () => {
    expect(getTotalPages(40, 20)).toBe(2);
  });

  it("counts a set smaller than one page as one page", () => {
    expect(getTotalPages(7, 20)).toBe(1);
  });

  it("counts an empty set as one page", () => {
    expect(getTotalPages(0, 20)).toBe(1);
  });
});

describe("clampPage", () => {
  it("keeps a page inside the range", () => {
    expect(clampPage(2, 3)).toBe(2);
  });

  it("clamps past the last page", () => {
    expect(clampPage(9, 3)).toBe(3);
  });

  it("clamps before the first page", () => {
    expect(clampPage(0, 3)).toBe(1);
  });
});

describe("getOffset", () => {
  it("the first page starts at offset zero", () => {
    expect(getOffset(1, 20)).toBe(0);
  });

  it("the last page starts after every preceding page", () => {
    expect(getOffset(3, 20)).toBe(40);
  });
});

describe("getPageWindow", () => {
  it("describes the first page of a larger set", () => {
    expect(getPageWindow(1, 20, 45)).toEqual({ firstRow: 1, lastRow: 20, totalCount: 45 });
  });

  it("describes a partial last page", () => {
    expect(getPageWindow(3, 20, 45)).toEqual({ firstRow: 41, lastRow: 45, totalCount: 45 });
  });

  it("describes a last page that is an exact multiple of the page size", () => {
    expect(getPageWindow(2, 20, 40)).toEqual({ firstRow: 21, lastRow: 40, totalCount: 40 });
  });

  it("describes a set smaller than one page", () => {
    expect(getPageWindow(1, 20, 7)).toEqual({ firstRow: 1, lastRow: 7, totalCount: 7 });
  });

  it("describes an empty set", () => {
    expect(getPageWindow(1, 20, 0)).toEqual({ firstRow: 0, lastRow: 0, totalCount: 0 });
  });

  it("describes the last page when asked for a page past the end", () => {
    expect(getPageWindow(8, 20, 45)).toEqual({ firstRow: 41, lastRow: 45, totalCount: 45 });
  });
});

describe("formatPageWindow", () => {
  it("states the window and the total on the first page", () => {
    expect(formatPageWindow(1, 20, 45)).toBe("Showing 1 to 20 of 45");
  });

  it("states the window and the total on the last page", () => {
    expect(formatPageWindow(3, 20, 45)).toBe("Showing 41 to 45 of 45");
  });

  it("states the whole set when it is smaller than one page", () => {
    expect(formatPageWindow(1, 20, 7)).toBe("Showing 1 to 7 of 7");
  });

  it("states a single row without a range", () => {
    expect(formatPageWindow(1, 20, 1)).toBe("Showing 1 of 1");
  });

  it("states an empty set", () => {
    expect(formatPageWindow(1, 20, 0)).toBe("Showing 0 of 0");
  });

  it("groups thousands", () => {
    expect(formatPageWindow(1, 20, 1234)).toBe("Showing 1 to 20 of 1,234");
  });
});

describe("getPageItems", () => {
  it("lists every page when they all fit", () => {
    expect(getPageItems(1, 3)).toEqual([1, 2, 3]);
  });

  it("lists the only page of a single-page set", () => {
    expect(getPageItems(1, 1)).toEqual([1]);
  });

  it("keeps the first and last page reachable from the middle", () => {
    expect(getPageItems(10, 20)).toEqual([1, "ellipsis", 9, 10, 11, "ellipsis", 20]);
  });

  it("elides only the far side on the first page", () => {
    expect(getPageItems(1, 20)).toEqual([1, 2, "ellipsis", 20]);
  });

  it("elides only the near side on the last page", () => {
    expect(getPageItems(20, 20)).toEqual([1, "ellipsis", 19, 20]);
  });
});
