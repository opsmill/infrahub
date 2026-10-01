import { beforeEach, describe, expect, test, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";

import { getRepositoryCommitStatusFromApi } from "./get-repository-commit-status-from-api";

vi.mock("@/shared/api/graphql/client", () => ({
  graphql: (query: string) => query,
  graphqlClient: { query: vi.fn() },
}));

describe("getRepositoryCommitStatusFromApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("queries the repository on the requested branch", async () => {
    // WHEN
    await getRepositoryCommitStatusFromApi({ repositoryId: "repo-1", branchName: "feature-x" });

    // THEN
    expect(graphqlClient.query).toHaveBeenCalledWith(
      expect.objectContaining({
        variables: { repositoryId: "repo-1" },
        context: { branch: "feature-x" },
      })
    );
  });
});
