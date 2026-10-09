import { afterEach, describe, expect, it, vi } from "vitest";

import { getNumberPoolAllocationsFromApi } from "@/entities/resource-manager/api/get-number-pool-allocations-from-api";

import { getNumberPoolAllocations } from "./get-number-pool-allocations";

vi.mock("@/entities/resource-manager/api/get-number-pool-allocations-from-api", () => ({
  getNumberPoolAllocationsFromApi: vi.fn(),
}));

type ApiResult = Awaited<ReturnType<typeof getNumberPoolAllocationsFromApi>>;

const params = { poolId: "pool-id", offset: 0, limit: 100, branchName: "main", atDate: null };

describe("getNumberPoolAllocations", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("returns the page of numbers", async () => {
    // GIVEN
    vi.mocked(getNumberPoolAllocationsFromApi).mockResolvedValue({
      data: {
        InfrahubNumberPoolAllocations: {
          allocations: [
            {
              value: 7,
              branch: "b1",
              provenance: "PROVIDED",
              holder: { id: "device-1", kind: "InfraDevice", display_label: "leaf-01" },
              range: { id: "range-1" },
            },
          ],
        },
      },
    } as unknown as ApiResult);

    // WHEN
    const result = await getNumberPoolAllocations(params);

    // THEN
    expect(result).toEqual([
      {
        value: 7,
        branch: "b1",
        provenance: "PROVIDED",
        holder: { id: "device-1", __typename: "InfraDevice", display_label: "leaf-01" },
        rangeId: "range-1",
      },
    ]);
  });

  it("throws the API errors", async () => {
    // GIVEN
    vi.mocked(getNumberPoolAllocationsFromApi).mockResolvedValue({
      data: undefined,
      errors: [{ message: "The pool has no range with this id" }],
    } as unknown as ApiResult);

    // WHEN
    const result = getNumberPoolAllocations(params);

    // THEN
    await expect(result).rejects.toThrow("The pool has no range with this id");
  });
});
