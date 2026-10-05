import { describe, expect, it } from "vitest";

import type { BranchRepository } from "@/entities/repository/domain/model/branch-repository";
import { getBranchRepositoriesQueryOptions } from "@/entities/repository/ui/queries/get-branch-repositories.query";
import { getBranchRepositoryHealthQueryOptions } from "@/entities/repository/ui/queries/get-branch-repository-health.query";

import {
  generateBranchRepository,
  generateBranchRepositoryHealth,
  SYNC_STATUS,
} from "../../../../../tests/fake/branch-repositories";

const pageParams = { branchName: "feature", syncWithGit: true, limit: 10, offset: 0 };

describe("getBranchRepositoryHealthQueryOptions", () => {
  const refetchIntervalFor = (
    syncingCount: number | undefined,
    status: "success" | "error" = "success"
  ) => {
    const { refetchInterval } = getBranchRepositoryHealthQueryOptions({
      branchName: "feature",
      syncWithGit: true,
    });
    if (typeof refetchInterval !== "function")
      throw new Error("refetchInterval must be a function");
    const data =
      syncingCount === undefined ? undefined : generateBranchRepositoryHealth({ syncingCount });
    return refetchInterval({ state: { data, status } } as unknown as Parameters<
      typeof refetchInterval
    >[0]);
  };

  it("polls every 10 seconds while the server counts a syncing repository", () => {
    expect(refetchIntervalFor(2)).toBe(10_000);
  });

  it("doesn't poll when none is syncing or nothing has loaded", () => {
    expect(refetchIntervalFor(0)).toBe(false);
    expect(refetchIntervalFor(undefined)).toBe(false);
  });

  it("slows the health check down once it has failed through its retries", () => {
    expect(refetchIntervalFor(undefined, "error")).toBe(60_000);
    expect(refetchIntervalFor(2, "error")).toBe(60_000);
  });
});

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

  it("slows the page poll down once a fetch has failed", () => {
    const { refetchInterval } = getBranchRepositoriesQueryOptions({
      ...pageParams,
      isSyncing: true,
    });
    if (typeof refetchInterval !== "function")
      throw new Error("refetchInterval must be a function");

    expect(
      refetchInterval({ state: { status: "error" } } as unknown as Parameters<
        typeof refetchInterval
      >[0])
    ).toBe(60_000);
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
    const placeholderFor = (previousParams: typeof pageParams) => {
      const { placeholderData } = getBranchRepositoriesQueryOptions({
        ...pageParams,
        offset: 10,
        isSyncing: false,
      });
      if (typeof placeholderData !== "function")
        throw new Error("placeholderData must be a function");
      const previousData = { repositories: [], count: 11 };
      const previousQuery = {
        queryKey: ["repository", "branch-repositories", previousParams],
      };
      return placeholderData(
        previousData,
        previousQuery as unknown as Parameters<typeof placeholderData>[1]
      );
    };

    it("keeps the previous page while the same list's next page loads", () => {
      expect(placeholderFor(pageParams)).toEqual({ repositories: [], count: 11 });
    });

    it("doesn't show another branch's or another list's rows", () => {
      expect(placeholderFor({ ...pageParams, branchName: "other" })).toBeUndefined();
      expect(placeholderFor({ ...pageParams, syncWithGit: false })).toBeUndefined();
    });
  });
});
