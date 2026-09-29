import { describe, expect, it } from "vitest";

import { getTaskRelatedLabel } from "./get-task-related-label";

const repositoriesById = new Map([
  ["repo-1", "infrahub-demo"],
  ["repo-2", "schema-library"],
]);

describe("getTaskRelatedLabel", () => {
  it("returns the name of a known repository", () => {
    const task = { relatedNodes: [{ id: "repo-1", kind: "CoreRepository" }] };

    expect(getTaskRelatedLabel(task, repositoriesById)).toBe("infrahub-demo");
  });

  it("returns the first known repository among several related nodes", () => {
    const task = {
      relatedNodes: [
        { id: "def-1", kind: "CoreGeneratorDefinition" },
        { id: "repo-2", kind: "CoreReadOnlyRepository" },
        { id: "repo-1", kind: "CoreRepository" },
      ],
    };

    expect(getTaskRelatedLabel(task, repositoriesById)).toBe("schema-library");
  });

  it("returns an em dash when the task has no related nodes", () => {
    expect(getTaskRelatedLabel({ relatedNodes: [] }, repositoriesById)).toBe("—");
  });

  it("returns the caller's empty label when the task has no related nodes", () => {
    expect(
      getTaskRelatedLabel({ relatedNodes: [] }, repositoriesById, undefined, "This branch")
    ).toBe("This branch");
  });

  it("returns the kind label of the first node when no repository is known", () => {
    const task = {
      relatedNodes: [
        { id: "def-1", kind: "CoreGeneratorDefinition" },
        { id: "node-1", kind: "InfraDevice" },
      ],
    };
    const getKindLabel = (kind: string) =>
      kind === "CoreGeneratorDefinition" ? "Generator Definition" : kind;

    expect(getTaskRelatedLabel(task, repositoriesById, getKindLabel)).toBe("Generator Definition");
  });

  it("returns the kind when no kind label resolver is given", () => {
    const task = { relatedNodes: [{ id: "def-1", kind: "CoreGeneratorDefinition" }] };

    expect(getTaskRelatedLabel(task, repositoriesById)).toBe("CoreGeneratorDefinition");
  });
});
