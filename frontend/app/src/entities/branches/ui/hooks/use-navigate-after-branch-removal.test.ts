import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { constructPath, getCurrentQsp } from "@/shared/api/rest/fetch";

import { useNavigateAfterBranchRemoval } from "./use-navigate-after-branch-removal";

const navigateMock = vi.fn();

vi.mock("react-router", () => ({
  useNavigate: () => navigateMock,
}));

vi.mock("@/shared/api/rest/fetch", () => ({
  constructPath: vi.fn(),
  getCurrentQsp: vi.fn(),
}));

vi.mock("@/shared/config/qsp", () => ({
  QSP: { BRANCH: "branch" },
}));

const constructPathMock = vi.mocked(constructPath);
const getCurrentQspMock = vi.mocked(getCurrentQsp);

describe("useNavigateAfterBranchRemoval", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("navigateToPage", () => {
    it("should strip branch QSP when deleted branch matches current branch", () => {
      // GIVEN
      getCurrentQspMock.mockReturnValue(new URLSearchParams("branch=feature-1"));
      constructPathMock.mockReturnValue("/branches");
      const { result } = renderHook(() => useNavigateAfterBranchRemoval());

      // WHEN
      result.current.navigateToPage("/branches", "feature-1");

      // THEN
      expect(constructPathMock).toHaveBeenCalledWith("/branches", [
        { name: "branch", exclude: true },
      ]);
      expect(navigateMock).toHaveBeenCalledWith("/branches");
    });

    it("should preserve branch QSP when deleted branch does not match current branch", () => {
      // GIVEN
      getCurrentQspMock.mockReturnValue(new URLSearchParams("branch=main"));
      constructPathMock.mockReturnValue("/branches?branch=main");
      const { result } = renderHook(() => useNavigateAfterBranchRemoval());

      // WHEN
      result.current.navigateToPage("/branches", "feature-1");

      // THEN
      expect(constructPathMock).toHaveBeenCalledWith("/branches");
      expect(navigateMock).toHaveBeenCalledWith("/branches?branch=main");
    });

    it("should preserve branch QSP when deletedBranchName is undefined", () => {
      // GIVEN
      getCurrentQspMock.mockReturnValue(new URLSearchParams("branch=main"));
      constructPathMock.mockReturnValue("/branches?branch=main");
      const { result } = renderHook(() => useNavigateAfterBranchRemoval());

      // WHEN
      result.current.navigateToPage("/branches");

      // THEN
      expect(constructPathMock).toHaveBeenCalledWith("/branches");
      expect(navigateMock).toHaveBeenCalledWith("/branches?branch=main");
    });

    it("should navigate when no branch QSP is set", () => {
      // GIVEN
      getCurrentQspMock.mockReturnValue(new URLSearchParams());
      constructPathMock.mockReturnValue("/branches");
      const { result } = renderHook(() => useNavigateAfterBranchRemoval());

      // WHEN
      result.current.navigateToPage("/branches", "feature-1");

      // THEN
      expect(constructPathMock).toHaveBeenCalledWith("/branches");
      expect(navigateMock).toHaveBeenCalledWith("/branches");
    });
  });

  describe("clearBranchIfCurrent", () => {
    it("should clear branch QSP when deleted branch matches current branch", () => {
      // GIVEN
      getCurrentQspMock.mockReturnValue(new URLSearchParams("branch=feature-1"));
      constructPathMock.mockReturnValue("/proposed-changes/123");
      Object.defineProperty(window, "location", {
        value: { pathname: "/proposed-changes/123" },
        writable: true,
      });
      const { result } = renderHook(() => useNavigateAfterBranchRemoval());

      // WHEN
      result.current.clearBranchIfCurrent("feature-1");

      // THEN
      expect(constructPathMock).toHaveBeenCalledWith("/proposed-changes/123", [
        { name: "branch", exclude: true },
      ]);
      expect(navigateMock).toHaveBeenCalledWith("/proposed-changes/123", { replace: true });
    });

    it("should not navigate when deleted branch does not match current branch", () => {
      // GIVEN
      getCurrentQspMock.mockReturnValue(new URLSearchParams("branch=main"));
      const { result } = renderHook(() => useNavigateAfterBranchRemoval());

      // WHEN
      result.current.clearBranchIfCurrent("feature-1");

      // THEN
      expect(navigateMock).not.toHaveBeenCalled();
    });

    it("should not navigate when deletedBranchName is undefined", () => {
      // GIVEN
      getCurrentQspMock.mockReturnValue(new URLSearchParams("branch=main"));
      const { result } = renderHook(() => useNavigateAfterBranchRemoval());

      // WHEN
      result.current.clearBranchIfCurrent();

      // THEN
      expect(navigateMock).not.toHaveBeenCalled();
    });
  });
});
