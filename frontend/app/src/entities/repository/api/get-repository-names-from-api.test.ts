import { beforeEach, describe, expect, it, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";

import { getRepositoryNamesFromApi } from "./get-repository-names-from-api";

vi.mock("@/shared/api/graphql/client", async () => ({
  graphql: (await import("gql.tada")).graphql,
  graphqlClient: { query: vi.fn() },
}));

const node = (id: string, name: string | null, displayLabel: string | null) => ({
  node: { id, display_label: displayLabel, name: name === null ? null : { value: name } },
});

describe("getRepositoryNamesFromApi", () => {
  const mockQuery = vi.mocked(graphqlClient.query);

  beforeEach(() => {
    mockQuery.mockReset();
  });

  it("sends the ids as variables, on the given branch", async () => {
    // GIVEN
    mockQuery.mockResolvedValueOnce({ data: { CoreGenericRepository: { edges: [] } } });

    // WHEN
    await getRepositoryNamesFromApi({ branchName: "feature", ids: ["repo-1", "task-node"] });

    // THEN
    expect(mockQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        variables: { ids: ["repo-1", "task-node"] },
        context: { branch: "feature" },
      })
    );
  });

  it("maps each repository id to its name, falling back to its display label", async () => {
    // GIVEN
    mockQuery.mockResolvedValueOnce({
      data: {
        CoreGenericRepository: {
          edges: [node("repo-1", "infra", "Infra (label)"), node("repo-2", null, "Vendor configs")],
        },
      },
    });

    // WHEN
    const names = await getRepositoryNamesFromApi({
      branchName: "feature",
      ids: ["repo-1", "repo-2", "not-a-repository"],
    });

    // THEN
    expect(names).toEqual({ "repo-1": "infra", "repo-2": "Vendor configs" });
  });

  it("leaves out ids the server doesn't return and nodes without a name", async () => {
    // GIVEN
    mockQuery.mockResolvedValueOnce({
      data: { CoreGenericRepository: { edges: [node("repo-1", null, null)] } },
    });

    // WHEN
    const names = await getRepositoryNamesFromApi({
      branchName: "feature",
      ids: ["repo-1", "not-a-repository"],
    });

    // THEN
    expect(names).toEqual({});
  });
});
