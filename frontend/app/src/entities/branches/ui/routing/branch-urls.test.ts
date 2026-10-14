import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { constructPath } from "@/shared/api/rest/fetch";

import { getBranchQsp } from "./branch-urls";

const withBranch = (path: string, branchName: string) =>
  constructPath(path, [getBranchQsp(branchName)]);

describe("getBranchQsp", () => {
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
    const url = withBranch("/objects/CoreRepository/123", "feature");

    // THEN
    expect(url).toBe("/objects/CoreRepository/123?branch=feature");
  });

  it("keeps the time-travel parameter", () => {
    // GIVEN
    window.history.replaceState(null, "", "/branches/feature?branch=main&at=2026-01-01T00:00:00Z");

    // WHEN
    const url = new URL(withBranch("/tasks", "feature"), window.location.origin);

    // THEN
    expect(url.pathname).toBe("/tasks");
    expect(url.searchParams.get("branch")).toBe("feature");
    expect(url.searchParams.get("at")).toBe("2026-01-01T00:00:00Z");
  });
});
