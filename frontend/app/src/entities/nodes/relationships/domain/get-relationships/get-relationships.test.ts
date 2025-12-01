import { beforeEach, describe, expect, it, vi } from "vitest";

import { getRelationshipsFromApi } from "@/entities/nodes/relationships/api/get-relationships-from-api";
import { getRelationships } from "@/entities/nodes/relationships/domain/get-relationships/get-relationships";

vi.mock("@/entities/nodes/relationships/api/get-relationships-from-api", () => ({
  getRelationshipsFromApi: vi.fn(),
}));

describe("getRelationships", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should fetch relationships with correct parameters", async () => {
    // GIVEN
    const peer = "test-peer";
    const offset = 0;
    const search = "search-term";
    const parentId = "parent-123";
    const branchName = "main";
    const atDate = new Date("2024-01-01");
    const mockResponse = {
      data: {
        "test-peer": {
          edges: [
            {
              node: {
                id: "1",
                hfid: ["test", "hfid", "1"],
                display_label: "Test Label",
                __typename: "TestType",
              },
            },
          ],
        },
      },
      loading: false,
      networkStatus: 7,
    };

    vi.mocked(getRelationshipsFromApi).mockResolvedValue(mockResponse);

    // WHEN
    const result = await getRelationships({
      peer,
      offset,
      search,
      filterQuery: {
        parent__ids: [parentId],
      },
      branchName,
      atDate,
    });

    // THEN
    expect(getRelationshipsFromApi).toHaveBeenCalledWith({
      peer,
      branchName,
      atDate,
      limit: 20,
      offset,
      search,
      filterQuery: {
        parent__ids: [parentId],
      },
    });
    expect(result).toEqual([
      {
        id: "1",
        hfid: ["test", "hfid", "1"],
        display_label: "Test Label",
        __typename: "TestType",
      },
    ]);
  });

  it("should fetch relationships without optional parameters", async () => {
    // GIVEN
    const peer = "test-peer";
    const branchName = "main";
    const atDate = new Date("2024-01-01");
    const mockResponse = {
      data: {
        "test-peer": {
          edges: [],
        },
      },
      loading: false,
      networkStatus: 7,
    };

    vi.mocked(getRelationshipsFromApi).mockResolvedValue(mockResponse);

    // WHEN
    const result = await getRelationships({ peer, branchName, atDate });

    // THEN
    expect(getRelationshipsFromApi).toHaveBeenCalledWith({
      peer,
      branchName,
      atDate,
      limit: 20,
      offset: undefined,
      search: undefined,
      filterQuery: undefined,
    });
    expect(result).toEqual([]);
  });
});
