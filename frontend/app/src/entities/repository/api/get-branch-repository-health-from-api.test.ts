import { print } from "graphql";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";

import { getBranchRepositoryHealthFromApi } from "./get-branch-repository-health-from-api";

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

describe("getBranchRepositoryHealthFromApi", () => {
  const mockQuery = vi.mocked(graphqlClient.query);
  const statuses = {
    importErrorStatuses: ["error-import"],
    unreachableStatuses: ["error-cred", "error-connection", "error"],
    syncingStatuses: ["syncing"],
    limit: 50,
  };

  beforeEach(() => {
    mockQuery.mockReset();
  });

  it("filters failing and syncing repositories on the server, capped, on the page's branch", async () => {
    // GIVEN
    const data = {
      importErrors: { count: 0, edges: [] },
      unreachable: { count: 0, edges: [] },
      syncing: { count: 2 },
    };
    mockQuery.mockResolvedValueOnce({ data });

    // WHEN
    const result = await getBranchRepositoryHealthFromApi({
      branchName: "feature",
      kind: "CoreGenericRepository",
      ...statuses,
    });

    // THEN
    expect(result).toBe(data);
    expect(mockQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        variables: statuses,
        context: { branch: "feature", processErrorMessage: expect.any(Function) },
      })
    );
    const query = sentQuery();
    expect(query).toMatch(
      /importErrors: CoreGenericRepository\(\s*sync_status__values: \$importErrorStatuses\s*limit: \$limit/
    );
    expect(query).toMatch(
      /unreachable: CoreGenericRepository\(\s*operational_status__values: \$unreachableStatuses\s*limit: \$limit/
    );
    expect(query).toMatch(
      /syncing: CoreGenericRepository\(sync_status__values: \$syncingStatuses\)/
    );
    expect(query).not.toMatch(/offset/);
  });

  it("filters read-only repositories only for the read-only kind", async () => {
    // GIVEN
    mockQuery.mockResolvedValueOnce({ data: {} });

    // WHEN
    await getBranchRepositoryHealthFromApi({
      branchName: "feature",
      kind: "CoreReadOnlyRepository",
      ...statuses,
    });

    // THEN
    expect(sentQuery()).toMatch(/importErrors: CoreReadOnlyRepository\(/);
    expect(sentQuery()).not.toMatch(/\w+: CoreGenericRepository\(/);
  });
});
