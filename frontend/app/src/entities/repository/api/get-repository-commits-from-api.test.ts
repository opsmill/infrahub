import { beforeEach, describe, expect, test, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";

import { getRepositoryCommitsFromApi } from "./get-repository-commits-from-api";

vi.mock("@/shared/api/graphql/client", () => ({
  graphql: (query: string) => query,
  graphqlClient: { query: vi.fn() },
}));

describe("getRepositoryCommitsFromApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("queries the requested page of the repository on the requested branch", async () => {
    // WHEN
    await getRepositoryCommitsFromApi({
      repositoryId: "repo-1",
      limit: 20,
      offset: 40,
      branchName: "feature-x",
    });

    // THEN
    expect(graphqlClient.query).toHaveBeenCalledWith(
      expect.objectContaining({
        variables: { repositoryId: "repo-1", limit: 20, offset: 40, isFirstPage: false },
        context: { branch: "feature-x", processErrorMessage: expect.any(Function) },
      })
    );
  });

  test.each([0, undefined])(
    "asks for the pending count on the first page (offset %s)",
    async (offset) => {
      // WHEN
      await getRepositoryCommitsFromApi({
        repositoryId: "repo-1",
        limit: 20,
        offset,
        branchName: "main",
      });

      // THEN
      expect(graphqlClient.query).toHaveBeenCalledWith(
        expect.objectContaining({ variables: expect.objectContaining({ isFirstPage: true }) })
      );
    }
  );
});
