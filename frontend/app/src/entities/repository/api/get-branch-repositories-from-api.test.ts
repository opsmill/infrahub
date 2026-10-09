import { print } from "graphql";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";

import { getBranchRepositoriesFromApi } from "./get-branch-repositories-from-api";

// `client` also re-exports gql.tada's `graphql` tag, which the module under test uses to build
// its queries. Keep that real and stub only the transport.
vi.mock("@/shared/api/graphql/client", async () => ({
  graphql: (await import("gql.tada")).graphql,
  graphqlClient: { query: vi.fn() },
}));

const sentQuery = () => {
  const args = vi.mocked(graphqlClient.query).mock.lastCall?.[0];
  return args ? print(args.query as Parameters<typeof print>[0]) : "";
};

describe("getBranchRepositoriesFromApi", () => {
  const mockQuery = vi.mocked(graphqlClient.query);

  beforeEach(() => {
    mockQuery.mockReset();
  });

  it("asks the server for one page ordered by name, on the page's branch", async () => {
    // GIVEN
    const connection = { count: 0, edges: [] };
    mockQuery.mockResolvedValueOnce({ data: { CoreGenericRepository: connection } });

    // WHEN
    const result = await getBranchRepositoriesFromApi({
      branchName: "feature",
      kind: "CoreGenericRepository",
      limit: 10,
      offset: 20,
    });

    // THEN
    expect(result).toBe(connection);
    expect(mockQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        variables: { limit: 10, offset: 20 },
        context: { branch: "feature", processErrorMessage: expect.any(Function) },
      })
    );
    expect(sentQuery()).toContain("CoreGenericRepository(");
    expect(sentQuery()).toMatch(/order: \{by: \[\{field: "name__value", direction: ASC\}\]\}/);
  });

  it("lists read-only repositories only for the read-only kind", async () => {
    // GIVEN
    const connection = { count: 0, edges: [] };
    mockQuery.mockResolvedValueOnce({ data: { CoreReadOnlyRepository: connection } });

    // WHEN
    const result = await getBranchRepositoriesFromApi({
      branchName: "feature",
      kind: "CoreReadOnlyRepository",
      limit: 10,
      offset: 0,
    });

    // THEN
    expect(result).toBe(connection);
    expect(sentQuery()).toContain("CoreReadOnlyRepository(");
  });

  it("lets a transport error through", async () => {
    // GIVEN
    const networkError = new TypeError("Failed to fetch");
    mockQuery.mockRejectedValueOnce(networkError);

    // WHEN / THEN
    await expect(
      getBranchRepositoriesFromApi({
        branchName: "feature",
        kind: "CoreGenericRepository",
        limit: 10,
        offset: 0,
      })
    ).rejects.toBe(networkError);
  });
});
