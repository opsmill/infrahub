import { describe, expect, it } from "vitest";

import {
  calculateDynamicPageSize,
  DEFAULT_PAGE_SIZE,
  DYNAMIC_PAGINATION_PERCENTAGE,
  DYNAMIC_PAGINATION_THRESHOLD,
  MAX_PAGE_SIZE,
  MIN_PAGE_SIZE,
} from "./pagination";

describe("pagination constants", () => {
  it("should have expected default values", () => {
    expect(DEFAULT_PAGE_SIZE).toBe(40);
    expect(MIN_PAGE_SIZE).toBe(40);
    expect(MAX_PAGE_SIZE).toBe(200);
    expect(DYNAMIC_PAGINATION_THRESHOLD).toBe(1000);
    expect(DYNAMIC_PAGINATION_PERCENTAGE).toBe(0.05);
  });
});

describe("calculateDynamicPageSize", () => {
  describe("when count is below threshold", () => {
    it("should return DEFAULT_PAGE_SIZE for count of 0", () => {
      expect(calculateDynamicPageSize(0)).toBe(DEFAULT_PAGE_SIZE);
    });

    it("should return DEFAULT_PAGE_SIZE for small counts", () => {
      expect(calculateDynamicPageSize(100)).toBe(DEFAULT_PAGE_SIZE);
      expect(calculateDynamicPageSize(500)).toBe(DEFAULT_PAGE_SIZE);
    });

    it("should return DEFAULT_PAGE_SIZE for count just below threshold", () => {
      expect(calculateDynamicPageSize(999)).toBe(DEFAULT_PAGE_SIZE);
    });
  });

  describe("when count is at or above threshold", () => {
    it("should calculate 5% of count at threshold", () => {
      // 5% of 1000 = 50
      expect(calculateDynamicPageSize(1000)).toBe(50);
    });

    it("should calculate 5% of count for larger datasets", () => {
      // 5% of 2000 = 100
      expect(calculateDynamicPageSize(2000)).toBe(100);
      // 5% of 3000 = 150
      expect(calculateDynamicPageSize(3000)).toBe(150);
    });

    it("should round up to nearest integer", () => {
      // 5% of 1001 = 50.05 -> 51
      expect(calculateDynamicPageSize(1001)).toBe(51);
      // 5% of 1234 = 61.7 -> 62
      expect(calculateDynamicPageSize(1234)).toBe(62);
    });
  });

  describe("when calculated size exceeds MAX_PAGE_SIZE", () => {
    it("should cap at MAX_PAGE_SIZE for very large datasets", () => {
      // 5% of 10000 = 500, capped at 200
      expect(calculateDynamicPageSize(10_000)).toBe(MAX_PAGE_SIZE);
      // 5% of 50000 = 2500, capped at 200
      expect(calculateDynamicPageSize(50_000)).toBe(MAX_PAGE_SIZE);
    });

    it("should cap at exactly MAX_PAGE_SIZE at the boundary", () => {
      // 5% of 4000 = 200, exactly at cap
      expect(calculateDynamicPageSize(4000)).toBe(MAX_PAGE_SIZE);
      // 5% of 4001 = 200.05 -> 201, capped at 200
      expect(calculateDynamicPageSize(4001)).toBe(MAX_PAGE_SIZE);
    });
  });

  describe("edge cases", () => {
    it("should handle negative counts by returning DEFAULT_PAGE_SIZE", () => {
      expect(calculateDynamicPageSize(-1)).toBe(DEFAULT_PAGE_SIZE);
      expect(calculateDynamicPageSize(-1000)).toBe(DEFAULT_PAGE_SIZE);
    });

    it("should return at least MIN_PAGE_SIZE for threshold values", () => {
      const result = calculateDynamicPageSize(DYNAMIC_PAGINATION_THRESHOLD);
      expect(result).toBeGreaterThanOrEqual(MIN_PAGE_SIZE);
    });

    it("should never exceed MAX_PAGE_SIZE", () => {
      const result = calculateDynamicPageSize(Number.MAX_SAFE_INTEGER);
      expect(result).toBeLessThanOrEqual(MAX_PAGE_SIZE);
    });
  });
});
