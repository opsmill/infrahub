import { beforeEach, describe, expect, it, vi } from "vitest";

import { constructPath, getCurrentQsp } from "@/shared/api/rest/fetch";

import { buildClearBranchIfCurrent, buildNavigateToPage } from "./use-navigate-after-branch-removal";

vi.mock("@/shared/api/rest/fetch", () => ({
  constructPath: vi.fn(),
  getCurrentQsp: vi.fn(),
}));

vi.mock("@/shared/config/qsp", () => ({
  QSP: { BRANCH: "branch" },
}));

const constructPathMock = vi.mocked(constructPath);
const getCurrentQspMock = vi.mocked(getCurrentQsp);

describe("buildNavigateToPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should strip branch QSP when deleted branch matches current branch", () => {
    // GIVEN
    const navigate = vi.fn();
    getCurrentQspMock.mockReturnValue(new URLSearchParams("branch=feature-1"));
    constructPathMock.mockReturnValue("/branches");
    const navigateToPage = buildNavigateToPage(navigate);

    // WHEN
    navigateToPage("/branches", "feature-1");

    // THEN
    expect(constructPathMock).toHaveBeenCalledWith("/branches", [
      { name: "branch", exclude: true },
    ]);
    expect(navigate).toHaveBeenCalledWith("/branches");
  });

  it("should preserve branch QSP when deleted branch does not match current branch", () => {
    // GIVEN
    const navigate = vi.fn();
    getCurrentQspMock.mockReturnValue(new URLSearchParams("branch=main"));
    constructPathMock.mockReturnValue("/branches?branch=main");
    const navigateToPage = buildNavigateToPage(navigate);

    // WHEN
    navigateToPage("/branches", "feature-1");

    // THEN
    expect(constructPathMock).toHaveBeenCalledWith("/branches");
    expect(navigate).toHaveBeenCalledWith("/branches?branch=main");
  });

  it("should preserve branch QSP when deletedBranchName is undefined", () => {
    // GIVEN
    const navigate = vi.fn();
    getCurrentQspMock.mockReturnValue(new URLSearchParams("branch=main"));
    constructPathMock.mockReturnValue("/branches?branch=main");
    const navigateToPage = buildNavigateToPage(navigate);

    // WHEN
    navigateToPage("/branches");

    // THEN
    expect(constructPathMock).toHaveBeenCalledWith("/branches");
    expect(navigate).toHaveBeenCalledWith("/branches?branch=main");
  });

  it("should navigate when no branch QSP is set", () => {
    // GIVEN
    const navigate = vi.fn();
    getCurrentQspMock.mockReturnValue(new URLSearchParams());
    constructPathMock.mockReturnValue("/branches");
    const navigateToPage = buildNavigateToPage(navigate);

    // WHEN
    navigateToPage("/branches", "feature-1");

    // THEN
    expect(constructPathMock).toHaveBeenCalledWith("/branches");
    expect(navigate).toHaveBeenCalledWith("/branches");
  });
});

describe("buildClearBranchIfCurrent", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should clear branch QSP when deleted branch matches current branch", () => {
    // GIVEN
    const navigate = vi.fn();
    getCurrentQspMock.mockReturnValue(new URLSearchParams("branch=feature-1"));
    constructPathMock.mockReturnValue("/proposed-changes/123");
    Object.defineProperty(window, "location", {
      value: { pathname: "/proposed-changes/123" },
      writable: true,
    });
    const clearBranchIfCurrent = buildClearBranchIfCurrent(navigate);

    // WHEN
    clearBranchIfCurrent("feature-1");

    // THEN
    expect(constructPathMock).toHaveBeenCalledWith("/proposed-changes/123", [
      { name: "branch", exclude: true },
    ]);
    expect(navigate).toHaveBeenCalledWith("/proposed-changes/123", { replace: true });
  });

  it("should not navigate when deleted branch does not match current branch", () => {
    // GIVEN
    const navigate = vi.fn();
    getCurrentQspMock.mockReturnValue(new URLSearchParams("branch=main"));
    const clearBranchIfCurrent = buildClearBranchIfCurrent(navigate);

    // WHEN
    clearBranchIfCurrent("feature-1");

    // THEN
    expect(navigate).not.toHaveBeenCalled();
  });

  it("should not navigate when deletedBranchName is undefined", () => {
    // GIVEN
    const navigate = vi.fn();
    getCurrentQspMock.mockReturnValue(new URLSearchParams("branch=main"));
    const clearBranchIfCurrent = buildClearBranchIfCurrent(navigate);

    // WHEN
    clearBranchIfCurrent();

    // THEN
    expect(navigate).not.toHaveBeenCalled();
  });
});
