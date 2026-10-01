import { describe, expect, test } from "vitest";

import {
  type RepositoryCommitLog,
  RepositoryCommitState,
  RepositoryGitCondition,
} from "@/entities/repository/domain/model/repository";
import { getCommitStatusFromLog } from "@/entities/repository/domain/rules/get-commit-status-from-log";

const LOG: RepositoryCommitLog = {
  repository_id: "repo-1",
  branch_name: "main",
  git_ref: "main",
  condition: RepositoryGitCondition.BEHIND,
  imported_commit: "a".repeat(40),
  remote_head: "b".repeat(40),
  pending_count: 3,
  fetched_at: null,
  checked_at: null,
  unavailable: null,
  commits: [
    {
      hash: "b".repeat(40),
      short_hash: "bbbbbbb",
      summary: "Head",
      author_name: "Ada",
      authored_at: "2026-01-01T00:00:00Z",
      state: RepositoryCommitState.HEAD,
    },
  ],
};

describe("getCommitStatusFromLog", () => {
  test("keeps only the condition and the pending count", () => {
    expect(getCommitStatusFromLog(LOG)).toEqual({
      condition: RepositoryGitCondition.BEHIND,
      pending_count: 3,
    });
  });

  test("carries an unavailable condition through", () => {
    expect(
      getCommitStatusFromLog({
        ...LOG,
        condition: RepositoryGitCondition.UNAVAILABLE,
        pending_count: null,
      })
    ).toEqual({ condition: RepositoryGitCondition.UNAVAILABLE, pending_count: null });
  });
});
