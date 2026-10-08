import { describe, expect, it } from "vitest";

import {
  BranchRepositoriesError,
  type BranchRepository,
  type BranchRepositoryPage,
} from "@/entities/repository/domain/model/branch-repository";
import { getBranchRepositoriesQueryOptions } from "@/entities/repository/ui/queries/get-branch-repositories.query";

import {
  generateBranchRepository,
  SYNC_STATUS,
} from "../../../../../tests/fake/branch-repositories";

const pageParams = { branchName: "feature", syncWithGit: true, limit: 10, offset: 0 };

describe("getBranchRepositoriesQueryOptions", () => {
  const pageRefetchIntervalFor = (isSyncing: boolean, rows: BranchRepository[] | undefined) => {
    const { refetchInterval } = getBranchRepositoriesQueryOptions({ ...pageParams, isSyncing });
    if (typeof refetchInterval !== "function")
      throw new Error("refetchInterval must be a function");
    const data = rows && { repositories: rows, count: rows.length };
    return refetchInterval({ state: { data } } as unknown as Parameters<typeof refetchInterval>[0]);
  };

  it("polls the page only while a repository is syncing", () => {
    expect(pageRefetchIntervalFor(true, [generateBranchRepository()])).toBe(10_000);
    expect(pageRefetchIntervalFor(false, [generateBranchRepository()])).toBe(false);
    expect(pageRefetchIntervalFor(false, undefined)).toBe(false);
  });

  it("stops polling once the user is denied, and keeps polling after any other failure", () => {
    const { refetchInterval } = getBranchRepositoriesQueryOptions({
      ...pageParams,
      isSyncing: true,
    });
    if (typeof refetchInterval !== "function")
      throw new Error("refetchInterval must be a function");
    const intervalAfter = (error: Error) =>
      refetchInterval({ state: { status: "error", error } } as unknown as Parameters<
        typeof refetchInterval
      >[0]);

    expect(intervalAfter(new BranchRepositoriesError("PERMISSION_DENIED", "Denied"))).toBe(false);
    expect(intervalAfter(new BranchRepositoriesError("UNKNOWN", "Offline"))).toBe(10_000);
  });

  it("fetches the page again after the sync ends while its rows still show it", () => {
    const stale = generateBranchRepository({ syncStatus: SYNC_STATUS.syncing });

    expect(pageRefetchIntervalFor(false, [stale])).toBe(10_000);
  });

  it("keys the page on its branch, list and window, not on the polling flag", () => {
    const syncing = getBranchRepositoriesQueryOptions({ ...pageParams, isSyncing: true });
    const idle = getBranchRepositoriesQueryOptions({ ...pageParams, isSyncing: false });

    expect(syncing.queryKey).toEqual(idle.queryKey);
    expect(syncing.queryKey).toEqual(["repository", "branch-repositories", pageParams]);
  });

  describe("placeholder data", () => {
    const placeholderFor = (
      previousParams: typeof pageParams,
      previousData: BranchRepositoryPage = { repositories: [generateBranchRepository()], count: 11 }
    ) => {
      const { placeholderData } = getBranchRepositoriesQueryOptions({
        ...pageParams,
        offset: 10,
        isSyncing: false,
      });
      if (typeof placeholderData !== "function")
        throw new Error("placeholderData must be a function");
      const previousQuery = {
        queryKey: ["repository", "branch-repositories", previousParams],
      };
      return placeholderData(
        previousData,
        previousQuery as unknown as Parameters<typeof placeholderData>[1]
      );
    };

    it("keeps the previous page while the same list's next page loads", () => {
      const previousData = { repositories: [generateBranchRepository()], count: 11 };

      expect(placeholderFor(pageParams, previousData)).toBe(previousData);
    });

    it("doesn't show another branch's or another list's rows", () => {
      expect(placeholderFor({ ...pageParams, branchName: "other" })).toBeUndefined();
      expect(placeholderFor({ ...pageParams, syncWithGit: false })).toBeUndefined();
    });

    it("doesn't keep a previous page without rows, such as a page past the end", () => {
      expect(placeholderFor(pageParams, { repositories: [], count: 11 })).toBeUndefined();
    });
  });
});
