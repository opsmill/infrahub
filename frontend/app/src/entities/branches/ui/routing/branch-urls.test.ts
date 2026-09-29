import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { withBranch } from "./branch-urls";

describe("withBranch", () => {
  let initialUrl: string;

  beforeEach(() => {
    initialUrl = window.location.href;
  });

  afterEach(() => {
    window.history.replaceState(null, "", initialUrl);
  });

  it("links to the page's branch when the selector is on another branch", () => {
    // GIVEN
    window.history.replaceState(null, "", "/branches/feature?branch=main");

    // WHEN
    const url = withBranch("/objects/CoreRepository/123", "feature", false);

    // THEN
    expect(url).toBe("/objects/CoreRepository/123?branch=feature");
  });

  it("keeps the time-travel parameter", () => {
    // GIVEN
    window.history.replaceState(null, "", "/branches/feature?branch=main&at=2026-01-01T00:00:00Z");

    // WHEN
    const url = new URL(withBranch("/tasks", "feature", false), window.location.origin);

    // THEN
    expect(url.pathname).toBe("/tasks");
    expect(url.searchParams.get("branch")).toBe("feature");
    expect(url.searchParams.get("at")).toBe("2026-01-01T00:00:00Z");
  });

  it("drops the branch parameter for the default branch", () => {
    // GIVEN
    window.history.replaceState(null, "", "/branches/main?branch=feature");

    // WHEN
    const url = withBranch("/objects/CoreRepository/123", "main", true);

    // THEN
    expect(url).toBe("/objects/CoreRepository/123");
  });
});
