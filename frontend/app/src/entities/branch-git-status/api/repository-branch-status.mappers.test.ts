import { describe, expect, it } from "vitest";

import { toRepositoryBranchGitStatusPage } from "@/entities/branch-git-status/api/repository-branch-status.mappers";

import { SYNC_STATUS } from "../../../../tests/fake/branch-repositories";

describe("toRepositoryBranchGitStatusPage", () => {
  it("maps each row's branch, commit and sync status, and keeps the server's count", () => {
    // WHEN
    const page = toRepositoryBranchGitStatusPage({
      count: 501,
      edges: [
        {
          node: {
            name: { value: "feature" },
            commit: { value: "abc123" },
            sync_status: SYNC_STATUS.importError,
          },
        },
      ],
    });

    // THEN
    expect(page).toEqual({
      rows: [{ branchName: "feature", commit: "abc123", syncStatus: SYNC_STATUS.importError }],
      count: 501,
    });
  });

  it.each([
    { name: "no sync status", sync_status: null },
    { name: "a sync status with no value", sync_status: { ...SYNC_STATUS.inSync, value: null } },
  ])("reads $name as no status, and a missing commit as none", ({ sync_status }) => {
    const page = toRepositoryBranchGitStatusPage({
      count: 1,
      edges: [{ node: { name: { value: "main" }, commit: null, sync_status } }],
    });

    expect(page.rows).toEqual([{ branchName: "main", commit: null, syncStatus: null }]);
  });
});
