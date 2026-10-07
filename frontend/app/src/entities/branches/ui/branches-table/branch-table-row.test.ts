import { describe, expect, it } from "vitest";

import type { BranchRepositorySummary } from "@/entities/branches/domain/model/branch-repository-summary";
import { toBranchTableRows } from "@/entities/branches/ui/branches-table/branch-table-row";

import { generateBranch } from "../../../../../tests/fake/branch";

describe("toBranchTableRows", () => {
  it("attaches each branch's summary by branch name, in branch order", () => {
    // GIVEN
    const main = generateBranch({ id: "b-main", name: "main" });
    const feature = generateBranch({ id: "b-feature", name: "feature" });
    const summaries: Record<string, BranchRepositorySummary> = {
      feature: { status: "denied" },
      main: { status: "ok", repositories: [], counts: [] },
    };

    // WHEN
    const rows = toBranchTableRows([main, feature], summaries);

    // THEN
    expect(rows).toEqual([
      { ...main, repositorySummary: { status: "ok", repositories: [], counts: [] } },
      { ...feature, repositorySummary: { status: "denied" } },
    ]);
  });

  it("marks a branch with no summary yet as pending", () => {
    // GIVEN
    const branch = generateBranch({ name: "new-branch" });

    // WHEN
    const [row] = toBranchTableRows([branch], {});

    // THEN
    expect(row?.repositorySummary).toEqual({ status: "pending" });
  });
});
