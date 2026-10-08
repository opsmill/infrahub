import { describe, expect, it } from "vitest";

import type { BranchGitStatus } from "@/entities/branch-git-status/domain/model/branch-git-status";
import { toBranchTableRows } from "@/entities/branches/ui/branches-table/branch-table-row";

import { generateBranch } from "../../../../../tests/fake/branch";

describe("toBranchTableRows", () => {
  it("attaches each branch's Git status by branch name, in branch order", () => {
    // GIVEN
    const main = generateBranch({ id: "b-main", name: "main" });
    const feature = generateBranch({ id: "b-feature", name: "feature" });
    const empty: BranchGitStatus = { status: "ok", repositories: [], counts: [], unloaded: [] };
    const gitStatuses: Record<string, BranchGitStatus> = {
      feature: { status: "denied" },
      main: empty,
    };

    // WHEN
    const rows = toBranchTableRows([main, feature], gitStatuses);

    // THEN
    expect(rows).toEqual([
      { ...main, gitStatus: empty },
      { ...feature, gitStatus: { status: "denied" } },
    ]);
  });

  it("marks a branch with no Git status yet as pending", () => {
    // GIVEN
    const branch = generateBranch({ name: "new-branch" });

    // WHEN
    const [row] = toBranchTableRows([branch], {});

    // THEN
    expect(row?.gitStatus).toEqual({ status: "pending" });
  });
});
