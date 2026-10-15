import { describe, expect, it } from "vitest";

import type { RepositoryActivityBranchOutcome } from "@/shared/api/graphql/generated/types";

import { countBranchOutcomes } from "@/entities/repository/domain/rules/count-branch-outcomes";

describe("countBranchOutcomes", () => {
  it("counts the changed and the failed branches", () => {
    expect(
      countBranchOutcomes([
        { branchName: "main", outcome: "IMPORTED" },
        { branchName: "feature-x", outcome: "FAILED" },
        { branchName: "feature-y", outcome: "FAILED" },
      ])
    ).toEqual({ changed: 1, failed: 2 });
  });

  it("counts an outcome the API added after this build as neither", () => {
    expect(
      countBranchOutcomes([
        { branchName: "main", outcome: "SKIPPED" as RepositoryActivityBranchOutcome },
      ])
    ).toEqual({ changed: 0, failed: 0 });
  });
});
