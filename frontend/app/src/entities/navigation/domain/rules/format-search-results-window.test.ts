import { describe, expect, test } from "vitest";

import { formatSearchResultsWindow } from "@/entities/navigation/domain/rules/format-search-results-window";

describe("formatSearchResultsWindow", () => {
  test("names the first and last listed rows", () => {
    // GIVEN
    const listedRows = { offset: 20, rowCount: 20 };

    // WHEN
    const text = formatSearchResultsWindow(listedRows);

    // THEN
    expect(text).toBe("Showing results 21 to 40");
  });

  test("names the only row of a page that lists one", () => {
    // GIVEN
    const listedRows = { offset: 40, rowCount: 1 };

    // WHEN
    const text = formatSearchResultsWindow(listedRows);

    // THEN
    expect(text).toBe("Showing result 41");
  });

  test("groups the digits of large row numbers", () => {
    // GIVEN
    const listedRows = { offset: 1000, rowCount: 20 };

    // WHEN
    const text = formatSearchResultsWindow(listedRows);

    // THEN
    expect(text).toBe("Showing results 1,001 to 1,020");
  });
});
