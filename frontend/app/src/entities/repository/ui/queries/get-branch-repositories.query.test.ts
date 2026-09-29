import { describe, expect, it } from "vitest";

import type { BranchRepositoriesResult } from "@/entities/repository/domain/model/branch-repository";
import { getBranchRepositoriesQueryOptions } from "@/entities/repository/ui/queries/get-branch-repositories.query";

import {
  generateBranchRepositoriesResult,
  generateBranchRepository,
  SYNC_STATUS,
} from "../../../../../tests/fake/branch-repositories";

const refetchIntervalFor = (data: BranchRepositoriesResult | undefined) => {
  const { refetchInterval } = getBranchRepositoriesQueryOptions({
    branchName: "feature",
    syncWithGit: true,
  });
  if (typeof refetchInterval !== "function") throw new Error("refetchInterval must be a function");
  return refetchInterval({ state: { data } } as unknown as Parameters<typeof refetchInterval>[0]);
};

describe("getBranchRepositoriesQueryOptions", () => {
  it("polls every 10 seconds while a repository is syncing", () => {
    const data = generateBranchRepositoriesResult([
      generateBranchRepository({ id: "a" }),
      generateBranchRepository({ id: "b", syncStatus: SYNC_STATUS.syncing }),
    ]);

    expect(refetchIntervalFor(data)).toBe(10_000);
  });

  it("doesn't poll when no repository is syncing", () => {
    const data = generateBranchRepositoriesResult([
      generateBranchRepository({ id: "a", syncStatus: SYNC_STATUS.importError }),
    ]);

    expect(refetchIntervalFor(data)).toBe(false);
  });

  it("doesn't poll when access is denied or nothing has loaded", () => {
    expect(refetchIntervalFor({ status: "denied" })).toBe(false);
    expect(refetchIntervalFor(undefined)).toBe(false);
  });
});
