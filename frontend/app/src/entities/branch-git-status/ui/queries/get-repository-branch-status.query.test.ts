import { describe, expect, test } from "vitest";

import { BranchGitStatusError } from "@/entities/branch-git-status/domain/model/branch-git-status";
import type { RepositoryBranchStatusPage } from "@/entities/branch-git-status/domain/model/repository-branch-status";
import { getRepositoryBranchStatusRefetchInterval } from "@/entities/branch-git-status/ui/queries/get-repository-branch-status.query";

import {
  generateRepositoryBranchStatus,
  generateRepositoryBranchStatusPage,
} from "../../../../../tests/fake/branch-git-status";
import { SYNC_STATUS } from "../../../../../tests/fake/branch-repositories";

const refetchIntervalFor = (data: RepositoryBranchStatusPage | undefined, error?: Error) =>
  getRepositoryBranchStatusRefetchInterval({
    state: { data, status: error ? "error" : "success", error: error ?? null },
  });

const syncingPage = (): RepositoryBranchStatusPage => ({
  rows: [
    generateRepositoryBranchStatus({ branchName: "main" }),
    generateRepositoryBranchStatus({ branchName: "feature", syncStatus: SYNC_STATUS.syncing }),
  ],
  count: 2,
});

describe("getRepositoryBranchStatusRefetchInterval", () => {
  test("polls every 10 seconds only while a row is syncing", () => {
    expect(refetchIntervalFor(syncingPage())).toBe(10_000);
    expect(refetchIntervalFor(generateRepositoryBranchStatusPage("main", "feature"))).toBe(false);
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
