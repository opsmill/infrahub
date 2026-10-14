import { describe, expect, test } from "vitest";

import { BranchGitStatusError } from "@/entities/branch-git-status/domain/model/branch-git-status";
import type { RepositoryBranchGitStatusPage } from "@/entities/branch-git-status/domain/model/repository-branch-git-status";
import { getRepositoryBranchStatusRefetchInterval } from "@/entities/branch-git-status/ui/queries/get-repository-branch-status.query";

import {
  generateRepositoryBranchGitStatus,
  generateRepositoryBranchGitStatusPage,
} from "../../../../../tests/fake/branch-git-status";
import { SYNC_STATUS } from "../../../../../tests/fake/branch-repositories";

const refetchIntervalFor = (data: RepositoryBranchGitStatusPage | undefined, error?: Error) =>
  getRepositoryBranchStatusRefetchInterval({
    state: { data, status: error ? "error" : "success", error: error ?? null },
  });

const syncingPage = (): RepositoryBranchGitStatusPage => ({
  rows: [
    generateRepositoryBranchGitStatus({ branchName: "main" }),
    generateRepositoryBranchGitStatus({ branchName: "feature", syncStatus: SYNC_STATUS.syncing }),
  ],
  count: 2,
});

describe("getRepositoryBranchStatusRefetchInterval", () => {
  test("polls every 10 seconds only while a row is syncing", () => {
    expect(refetchIntervalFor(syncingPage())).toBe(10_000);
    expect(
      refetchIntervalFor(
        generateRepositoryBranchGitStatusPage({ branchNames: ["main", "feature"] })
      )
    ).toBe(false);
    expect(refetchIntervalFor(undefined)).toBe(false);
  });

  test("polls a failed read every minute", () => {
    expect(refetchIntervalFor(undefined, new Error("Network error"))).toBe(60_000);
  });

  test("stops polling once the reader is denied", () => {
    const denied = new BranchGitStatusError("PERMISSION_DENIED", "Permission denied");
    expect(refetchIntervalFor(syncingPage(), denied)).toBe(false);
  });
});
