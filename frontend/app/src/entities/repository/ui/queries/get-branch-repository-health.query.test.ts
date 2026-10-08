import { describe, expect, it } from "vitest";

import { BranchRepositoriesError } from "@/entities/repository/domain/model/branch-repository";
import { getBranchRepositoryHealthQueryOptions } from "@/entities/repository/ui/queries/get-branch-repository-health.query";

import { generateBranchRepositoryHealth } from "../../../../../tests/fake/branch-repositories";

const refetchIntervalFor = (syncingCount: number | undefined, error: Error | null = null) => {
  const { refetchInterval } = getBranchRepositoryHealthQueryOptions({
    branchName: "feature",
    syncWithGit: true,
  });
  if (typeof refetchInterval !== "function") throw new Error("refetchInterval must be a function");
  const data =
    syncingCount === undefined ? undefined : generateBranchRepositoryHealth({ syncingCount });
  return refetchInterval({ state: { data, error } } as unknown as Parameters<
    typeof refetchInterval
  >[0]);
};

describe("getBranchRepositoryHealthQueryOptions", () => {
  it("keys the check on the branch and the list", () => {
    expect(
      getBranchRepositoryHealthQueryOptions({ branchName: "feature", syncWithGit: false }).queryKey
    ).toEqual(["repository", "branch-health", { branchName: "feature", syncWithGit: false }]);
  });

  it("polls every 10 seconds while the server counts a syncing repository", () => {
    expect(refetchIntervalFor(2)).toBe(10_000);
  });

  it("doesn't poll when none is syncing or nothing has loaded", () => {
    expect(refetchIntervalFor(0)).toBe(false);
    expect(refetchIntervalFor(undefined)).toBe(false);
  });

  it("keeps polling after a failed check during a sync, and stops once the user is denied", () => {
    expect(refetchIntervalFor(2, new BranchRepositoriesError("UNKNOWN", "Offline"))).toBe(10_000);
    expect(refetchIntervalFor(2, new BranchRepositoriesError("PERMISSION_DENIED", "Denied"))).toBe(
      false
    );
  });
});
