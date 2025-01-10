import { getCurrentBranchName } from "@/entities/branches/get-current-branch";
import { getRelationshipsFromApi } from "@/entities/nodes/relationships/api/queries";
import { getRelationships } from "@/entities/nodes/relationships/domain/get-relationships/get-relationships";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/entities/branches/get-current-branch");
vi.mock("@/entities/nodes/relationships/api/queries");
vi.mock("@/shared/stores");

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
    const mockBranch = "main";
    const mockDate = "2024-01-01";
    const mockResponse = {
      data: {
        "test-peer": {
          edges: [
            {
              node: {
                id: "1",
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

    vi.mocked(getCurrentBranchName).mockReturnValue(mockBranch);
    vi.mocked(store.get).mockReturnValue(mockDate);
    vi.mocked(getRelationshipsFromApi).mockResolvedValue(mockResponse);

    // WHEN
    const result = await getRelationships({ peer, offset, search, parentId });

    // THEN
    expect(getCurrentBranchName).toHaveBeenCalledOnce();
    expect(store.get).toHaveBeenCalledWith(datetimeAtom);
    expect(getRelationshipsFromApi).toHaveBeenCalledWith({
      peer,
      limit: 20,
      offset,
      search,
      branchName: mockBranch,
      atDate: mockDate,
      parent: { name: "parent", value: parentId },
    });
    expect(result).toEqual([
      {
        id: "1",
        display_label: "Test Label",
        __typename: "TestType",
      },
    ]);
  });

  it("should fetch relationships without optional parameters", async () => {
    // GIVEN
    const peer = "test-peer";
    const mockBranch = "main";
    const mockDate = "2024-01-01";
    const mockResponse = {
      data: {
        "test-peer": {
          edges: [],
        },
      },
      loading: false,
      networkStatus: 7,
    };

    vi.mocked(getCurrentBranchName).mockReturnValue(mockBranch);
    vi.mocked(store.get).mockReturnValue(mockDate);
    vi.mocked(getRelationshipsFromApi).mockResolvedValue(mockResponse);

    // WHEN
    const result = await getRelationships({ peer });

    // THEN
    expect(getRelationshipsFromApi).toHaveBeenCalledWith({
      peer,
      limit: 20,
      offset: undefined,
      search: undefined,
      branchName: mockBranch,
      atDate: mockDate,
      parent: undefined,
    });
    expect(result).toEqual([]);
  });
});
