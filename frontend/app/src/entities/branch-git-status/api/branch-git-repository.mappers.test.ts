import { describe, expect, it } from "vitest";

import { toBranchGitRepositoryPage } from "@/entities/branch-git-status/api/branch-git-repository.mappers";

describe("toBranchGitRepositoryPage", () => {
  it("maps each repository with its kind and keeps the server's count", () => {
    // WHEN
    const page = toBranchGitRepositoryPage({
      count: 12,
      edges: [
        { node: { id: "r1", __typename: "CoreRepository", name: { value: "configs" } } },
        { node: { id: "r2", __typename: "CoreReadOnlyRepository", name: { value: "golden" } } },
      ],
    });

    // THEN
    expect(page).toEqual({
      repositories: [
        { id: "r1", name: "configs", kind: "CoreRepository", isReadOnly: false },
        { id: "r2", name: "golden", kind: "CoreReadOnlyRepository", isReadOnly: true },
      ],
      count: 12,
    });
  });

  it("names a repository by its id when it has no name", () => {
    const page = toBranchGitRepositoryPage({
      count: 1,
      edges: [{ node: { id: "r1", __typename: "CoreRepository", name: null } }],
    });

    expect(page.repositories[0]?.name).toBe("r1");
  });

  it("drops an edge with no node", () => {
    const page = toBranchGitRepositoryPage({ count: 1, edges: [{ node: null }] });

    expect(page.repositories).toEqual([]);
  });
});
