import { describe, expect, test, vi } from "vitest";

import { searchAnywhere } from "@/entities/navigation/domain/use-cases/search-anywhere";

const searchAnywhereFromApi = vi.hoisted(() => vi.fn());

vi.mock("@/entities/navigation/api/search-from-api", () => ({ searchAnywhereFromApi }));

const nodes = (count: number) =>
  Array.from({ length: count }, (_, index) => ({
    node: { id: `id-${index}`, kind: "InfraDevice" },
  }));

const respondWith = (count: number) =>
  searchAnywhereFromApi.mockResolvedValue({
    data: { InfrahubSearchAnywhere: { edges: nodes(count), parent_prefixes: null } },
  });

describe("searchAnywhere", () => {
  test("reports more results when the API returns more rows than the limit", async () => {
    // GIVEN
    respondWith(3);

    // WHEN
    const result = await searchAnywhere({ branchName: "main", search: "atl", limit: 2 });

    // THEN
    expect(searchAnywhereFromApi).toHaveBeenCalledWith(expect.objectContaining({ limit: 3 }));
    expect(result.matchingObjects.map(({ id }) => id)).toEqual(["id-0", "id-1"]);
    expect(result.hasMore).toBe(true);
  });

  test("reports no more results when the API returns up to the limit", async () => {
    // GIVEN
    respondWith(2);

    // WHEN
    const result = await searchAnywhere({ branchName: "main", search: "atl", limit: 2 });

    // THEN
    expect(result.matchingObjects).toHaveLength(2);
    expect(result.hasMore).toBe(false);
  });
});
