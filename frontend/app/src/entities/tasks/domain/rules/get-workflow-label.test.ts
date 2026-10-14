import { describe, expect, it } from "vitest";

import { getWorkflowLabel } from "./get-workflow-label";

describe("getWorkflowLabel", () => {
  it("returns the short label of a known workflow, whatever its id's spelling", () => {
    expect(getWorkflowLabel("git-repository-add-read-write")).toBe("Import");
    expect(getWorkflowLabel("git_repositories_sync")).toBe("Sync");
  });

  it("returns an em dash when there is no workflow", () => {
    expect(getWorkflowLabel(null)).toBe("—");
  });

  it("humanizes the id of an unknown workflow", () => {
    expect(getWorkflowLabel("some-new_workflow")).toBe("Some new workflow");
  });

  it.each([
    ["constructor", "Constructor"],
    ["toString", "ToString"],
    ["__proto__", "Proto"],
  ])("humanizes %s instead of reading an inherited object property", (workflow, label) => {
    expect(getWorkflowLabel(workflow)).toBe(label);
  });
});
