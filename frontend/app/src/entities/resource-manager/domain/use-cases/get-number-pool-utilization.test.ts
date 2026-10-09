import { afterEach, describe, expect, it, vi } from "vitest";

import { getNumberPoolUtilizationFromApi } from "@/entities/resource-manager/api/get-number-pool-utilization-from-api";

import { getNumberPoolUtilization } from "./get-number-pool-utilization";

vi.mock("@/entities/resource-manager/api/get-number-pool-utilization-from-api", () => ({
  getNumberPoolUtilizationFromApi: vi.fn(),
}));

type ApiResult = Awaited<ReturnType<typeof getNumberPoolUtilizationFromApi>>;

const params = { poolId: "pool-id", branchName: "main", atDate: null };

const figures = { size: 50, used: 0, used_default_branch: 0, used_branches: 0, utilization: 0 };

describe("getNumberPoolUtilization", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("returns the ranges in the order the pool fills them", async () => {
    // GIVEN
    vi.mocked(getNumberPoolUtilizationFromApi).mockResolvedValue({
      data: {
        InfrahubNumberPoolUtilization: {
          figures: { ...figures, size: 100 },
          ranges: [
            { id: "by-start", start: 1, end: 50, weight: 0, figures },
            { id: "by-weight", start: 51, end: 100, weight: 10, figures },
          ],
        },
      },
    } as unknown as ApiResult);

    // WHEN
    const utilization = await getNumberPoolUtilization(params);

    // THEN
    expect(utilization.ranges.map(({ id }) => id)).toEqual(["by-weight", "by-start"]);
  });

  it("throws the API errors", async () => {
    // GIVEN
    vi.mocked(getNumberPoolUtilizationFromApi).mockResolvedValue({
      data: undefined,
      errors: [{ message: "first" }, { message: "second" }],
    } as unknown as ApiResult);

    // WHEN
    const result = getNumberPoolUtilization(params);

    // THEN
    await expect(result).rejects.toThrow("first; second");
  });
});
