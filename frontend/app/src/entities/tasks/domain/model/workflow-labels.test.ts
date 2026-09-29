import { describe, expect, it } from "vitest";

import { getWorkflowLabel } from "./workflow-labels";

describe("getWorkflowLabel", () => {
  it.each([
    ["git-repository-add-read-write", "Import"],
    ["git-repository-add-read-only", "Import"],
    ["git-repository-import-object", "Import"],
    ["git-read-only-repository-import-last-commit", "Import"],
    ["git-repository-pull-read-only", "Import"],
    ["sync-git-repo-with-origin", "Sync"],
    ["git_repositories_sync", "Sync"],
    ["generator-run", "Generator"],
    ["generator-definition-run", "Generator"],
    ["request-generator-definition-run", "Generator"],
    ["artifact-generate", "Artifacts"],
    ["artifact-definition-generate", "Artifacts"],
    ["request_artifact_definitions_generate", "Artifacts"],
    ["git-repository-check-artifact-create", "Artifacts"],
    ["branch-validate", "Validate"],
    ["branch-rebase", "Rebase"],
    ["merge-branch-mutation", "Merge"],
    ["branch-merge", "Merge"],
    ["git-repository-merge", "Merge"],
    ["create-branch", "Create branch"],
    ["git-repository-trigger-user-checks", "Checks"],
    ["schema_validate_migrations", "Schema"],
    ["proposed-changed-run-generator", "Proposed change"],
    ["computed_attribute_process_transform", "Computed attribute"],
  ])("maps %s to %s", (workflow, label) => {
    expect(getWorkflowLabel(workflow)).toBe(label);
  });

  it("returns an em dash when there is no workflow", () => {
    expect(getWorkflowLabel(null)).toBe("—");
  });

  it("humanizes the id of an unknown workflow", () => {
    expect(getWorkflowLabel("some-new_workflow")).toBe("Some new workflow");
  });
});
