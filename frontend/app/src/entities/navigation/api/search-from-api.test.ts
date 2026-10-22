import { beforeEach, describe, expect, it, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";

import { searchAnywhereFromApi } from "./search-from-api";

vi.mock("@/shared/api/graphql/client", async () => ({
  graphql: (await import("gql.tada")).graphql,
  graphqlClient: { query: vi.fn() },
}));

describe("searchAnywhereFromApi", () => {
  const mockQuery = vi.mocked(graphqlClient.query);

  beforeEach(() => {
    mockQuery.mockReset();
  });

  it("asks for partial matches by default", async () => {
    // GIVEN
    const params = { branchName: "main", atDate: null, search: "atl1", limit: 4 };

    // WHEN
    await searchAnywhereFromApi(params);

    // THEN
    expect(mockQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        variables: { search: "atl1", limit: 4, caseSensitive: undefined, partialMatch: true },
      })
    );
  });

  it("turns partial matching off when exact match is on", async () => {
    // GIVEN
    const params = {
      branchName: "main",
      atDate: null,
      search: "atl1",
      limit: 4,
      caseSensitive: true,
      exactMatch: true,
    };

    // WHEN
    await searchAnywhereFromApi(params);

    // THEN
    expect(mockQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        variables: { search: "atl1", limit: 4, caseSensitive: true, partialMatch: false },
      })
    );
  });
});
