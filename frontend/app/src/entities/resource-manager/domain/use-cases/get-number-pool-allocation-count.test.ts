import { afterEach, describe, expect, it, vi } from "vitest";

import { getNumberPoolAllocationCountFromApi } from "@/entities/resource-manager/api/get-number-pool-allocation-count-from-api";

import { getNumberPoolAllocationCount } from "./get-number-pool-allocation-count";

vi.mock("@/entities/resource-manager/api/get-number-pool-allocation-count-from-api", () => ({
  getNumberPoolAllocationCountFromApi: vi.fn(),
}));

type ApiResult = Awaited<ReturnType<typeof getNumberPoolAllocationCountFromApi>>;

const params = { poolId: "pool-id", branchName: "main", atDate: null };

describe("getNumberPoolAllocationCount", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("returns the number of allocations as a number", async () => {
    // GIVEN
    vi.mocked(getNumberPoolAllocationCountFromApi).mockResolvedValue({
      data: { InfrahubNumberPoolAllocations: { count: "250" } },
    } as unknown as ApiResult);

    // WHEN
    const result = await getNumberPoolAllocationCount(params);

    // THEN
    expect(result).toBe(250);
  });

  it("throws the API errors", async () => {
    // GIVEN
    vi.mocked(getNumberPoolAllocationCountFromApi).mockResolvedValue({
      data: undefined,
      errors: [{ message: "The pool has no range with this id" }],
    } as unknown as ApiResult);

    // WHEN
    const result = getNumberPoolAllocationCount(params);

    // THEN
    await expect(result).rejects.toThrow("The pool has no range with this id");
  });
});
