import { beforeEach, describe, expect, it, vi } from "vitest";

import { searchAnywhereFromApi } from "@/entities/navigation/api/search-from-api";

import { searchAnywhere } from "./search-anywhere";

vi.mock("@/entities/navigation/api/search-from-api");

const node = (id: string) => ({ node: { id, kind: "InfraDevice" } });

const apiResponse = (ids: Array<string>) =>
  ({
    data: { InfrahubSearchAnywhere: { edges: ids.map(node), parent_prefixes: null } },
    errors: undefined,
  }) as unknown as Awaited<ReturnType<typeof searchAnywhereFromApi>>;

describe("searchAnywhere", () => {
  const mockSearch = vi.mocked(searchAnywhereFromApi);

  beforeEach(() => {
    mockSearch.mockReset();
  });

  it("asks the API for one result past the limit", async () => {
    // GIVEN
    mockSearch.mockResolvedValueOnce(apiResponse([]));

    // WHEN
    await searchAnywhere({ branchName: "main", search: "atl1", limit: 4 });

    // THEN
    expect(mockSearch).toHaveBeenCalledWith(expect.objectContaining({ limit: 5 }));
  });

  it("returns the limit and reports more results when the API returns one past it", async () => {
    // GIVEN
    mockSearch.mockResolvedValueOnce(apiResponse(["a", "b", "c", "d", "e"]));

    // WHEN
    const result = await searchAnywhere({ branchName: "main", search: "atl1", limit: 4 });

    // THEN
    expect(result).toEqual({
      matchingObjects: ["a", "b", "c", "d"].map((id) => ({ id, kind: "InfraDevice" })),
      hasMore: true,
      parentPrefixes: null,
    });
  });

  it("reports no more results when the API returns at most the limit", async () => {
    // GIVEN
    mockSearch.mockResolvedValueOnce(apiResponse(["a", "b", "c", "d"]));

    // WHEN
    const result = await searchAnywhere({ branchName: "main", search: "atl1", limit: 4 });

    // THEN
    expect(result.hasMore).toBe(false);
  });
});
