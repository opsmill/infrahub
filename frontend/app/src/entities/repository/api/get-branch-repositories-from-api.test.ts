import { CombinedError } from "@urql/core";
import { GraphQLError } from "graphql";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";

import { getBranchRepositoriesFromApi } from "./get-branch-repositories-from-api";

// `client` also re-exports gql.tada's `graphql` tag, which the module under test uses to build
// the query. Keep that real and stub only the transport.
vi.mock("@/shared/api/graphql/client", async () => ({
  graphql: (await import("gql.tada")).graphql,
  graphqlClient: { query: vi.fn() },
}));

describe("getBranchRepositoriesFromApi", () => {
  const mockQuery = vi.mocked(graphqlClient.query);

  beforeEach(() => {
    mockQuery.mockReset();
  });

  it("returns the connection of the requested kind on the page's branch", async () => {
    const connection = { count: 0, edges: [] };
    mockQuery.mockResolvedValueOnce({ data: { CoreReadOnlyRepository: connection } });

    const result = await getBranchRepositoriesFromApi({
      branchName: "feature",
      kind: "CoreReadOnlyRepository",
    });

    expect(result).toEqual({ data: connection });
    expect(mockQuery).toHaveBeenCalledWith(
      expect.objectContaining({ context: { branch: "feature" } })
    );
  });

  it("hands GraphQL errors back with their extensions instead of throwing", async () => {
    const graphQLError = new GraphQLError("You do not have one of the following permissions", {
      extensions: { code: "PERMISSION_DENIED", http_status: 403 },
    });
    mockQuery.mockRejectedValueOnce(
      new Error(graphQLError.message, {
        cause: new CombinedError({ graphQLErrors: [graphQLError] }),
      })
    );

    const result = await getBranchRepositoriesFromApi({
      branchName: "feature",
      kind: "CoreGenericRepository",
    });

    expect(result.data).toBeUndefined();
    expect(result.errors).toHaveLength(1);
    expect(result.errors?.[0]).toMatchObject({
      message: "You do not have one of the following permissions",
      extensions: { code: "PERMISSION_DENIED", http_status: 403 },
    });
  });

  it("rethrows an error that doesn't come from GraphQL", async () => {
    const networkError = new TypeError("Failed to fetch");
    mockQuery.mockRejectedValueOnce(networkError);

    await expect(
      getBranchRepositoriesFromApi({ branchName: "feature", kind: "CoreGenericRepository" })
    ).rejects.toBe(networkError);
  });
});
