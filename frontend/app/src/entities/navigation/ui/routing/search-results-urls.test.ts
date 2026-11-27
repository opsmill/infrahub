import { afterEach, describe, expect, test } from "vitest";

import { getSearchResultsUrl } from "@/entities/navigation/ui/routing/search-results-urls";

const initialUrl = `${window.location.pathname}${window.location.search}`;

describe("getSearchResultsUrl", () => {
  afterEach(() => {
    window.history.replaceState(null, "", initialUrl);
  });

  test("leaves out case sensitivity when the search ignores case", () => {
    // GIVEN
    window.history.replaceState(null, "", "/");

    // WHEN
    const url = getSearchResultsUrl({ search: "atl", caseSensitive: false });

    // THEN
    expect(url).toBe("/search?q=atl");
  });

  test("keeps case sensitivity when the search uses it", () => {
    // GIVEN
    window.history.replaceState(null, "", "/");

    // WHEN
    const url = getSearchResultsUrl({ search: "atl", caseSensitive: true });

    // THEN
    expect(url).toBe("/search?q=atl&case_sensitive=true");
  });

  test("keeps the branch and the time of the current page", () => {
    // GIVEN
    window.history.replaceState(null, "", "/objects/InfraDevice?branch=feature&at=2026-11-01");

    // WHEN
    const url = getSearchResultsUrl({ search: "atl", caseSensitive: false });

    // THEN
    expect(url).toBe("/search?q=atl&branch=feature&at=2026-11-01");
  });

  test("keeps characters that have a meaning in a URL as part of the search text", () => {
    // GIVEN
    window.history.replaceState(null, "", "/");

    // WHEN
    const url = new URL(
      getSearchResultsUrl({ search: "a&b=c #d?", caseSensitive: false }),
      window.location.origin
    );

    // THEN
    expect([...url.searchParams]).toEqual([["q", "a&b=c #d?"]]);
  });
});
