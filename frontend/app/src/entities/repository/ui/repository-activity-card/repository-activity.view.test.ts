import { describe, expect, it } from "vitest";

import type { RepositoryActivityOperation } from "@/shared/api/graphql/generated/types";

import {
  getOperationLabel,
  getRunOutcomeParts,
  getRunProgressText,
} from "@/entities/repository/ui/repository-activity-card/repository-activity.view";

import { generateActiveRun, generateLastRun } from "../../../../../tests/fake/repository-activity";

describe("getOperationLabel", () => {
  it("uses the wording written for a known operation", () => {
    expect(getOperationLabel("BRANCH_CREATE")).toBe("Branch creation");
  });

  it("reads an operation the API added after this build from its enum name", () => {
    expect(getOperationLabel("DRIFT_CHECK" as RepositoryActivityOperation)).toBe("Drift check");
  });
});

describe("getRunProgressText", () => {
  it("names the step and the branch it works on", () => {
    expect(getRunProgressText(generateActiveRun({ phase: "APPLYING", branchName: "main" }))).toBe(
      "Applying main"
    );
  });

  it("says a fetch covers every branch", () => {
    expect(getRunProgressText(generateActiveRun({ phase: "FETCHING", branchName: null }))).toBe(
      "Fetching all branches"
    );
  });

  it("shows only the branch for a run without steps", () => {
    expect(getRunProgressText(generateActiveRun({ phase: null, branchName: "feature-x" }))).toBe(
      "feature-x"
    );
  });

  it("shows nothing before a run reports its first step", () => {
    expect(getRunProgressText(generateActiveRun({ phase: null, branchName: null }))).toBe("");
  });
});

describe("getRunOutcomeParts", () => {
  it("names the branch when the run touched one", () => {
    const run = generateLastRun({ branches: [{ branchName: "main", outcome: "FAILED" }] });

    expect(getRunOutcomeParts(run)).toEqual({ failed: "main failed", changed: null });
  });

  it("counts branches when the run touched several", () => {
    const run = generateLastRun({
      branches: [
        { branchName: "main", outcome: "IMPORTED" },
        { branchName: "release-1.12", outcome: "IMPORTED" },
        { branchName: "feature-x", outcome: "FAILED" },
      ],
    });

    expect(getRunOutcomeParts(run)).toEqual({ failed: "1 failed", changed: "2 changed" });
  });

  it("has nothing to report when the run changed no branch", () => {
    expect(getRunOutcomeParts(generateLastRun({ branches: [] }))).toEqual({
      failed: null,
      changed: null,
    });
  });
});
