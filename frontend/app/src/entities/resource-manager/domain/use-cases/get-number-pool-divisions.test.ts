import { afterEach, describe, expect, it, vi } from "vitest";

import { getNumberPoolDivisionsFromApi } from "@/entities/resource-manager/api/get-number-pool-divisions-from-api";

import { getNumberPoolDivisions } from "./get-number-pool-divisions";

vi.mock("@/entities/resource-manager/api/get-number-pool-divisions-from-api", () => ({
  getNumberPoolDivisionsFromApi: vi.fn(),
}));

type ApiResult = Awaited<ReturnType<typeof getNumberPoolDivisionsFromApi>>;

const params = { poolId: "pool-id", branchName: "main", atDate: null };

const figures = { size: 50, used: 5, used_default_branch: 5, used_branches: 0, utilization: 10 };

describe("getNumberPoolDivisions", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("returns the allocation scopes of the pool", async () => {
    // GIVEN
    vi.mocked(getNumberPoolDivisionsFromApi).mockResolvedValue({
      data: {
        InfrahubNumberPoolDivisions: {
          allocation_scope: [{ id: "field-1", name: "device" }],
          count: 1,
          divisions: [
            {
              display_label: "atl1-core1",
              entries: [
                {
                  path: "device",
                  value: "device-id",
                  display_label: "atl1-core1",
                  peer_kind: "InfraDevice",
                },
              ],
              figures,
            },
          ],
        },
      },
    } as unknown as ApiResult);

    // WHEN
    const result = await getNumberPoolDivisions(params);

    // THEN
    expect(result.fields).toEqual(["device"]);
    expect(result.divisions.map(({ label }) => label)).toEqual(["atl1-core1"]);
  });

  it("throws the API errors", async () => {
    // GIVEN
    vi.mocked(getNumberPoolDivisionsFromApi).mockResolvedValue({
      data: undefined,
      errors: [{ message: "first" }, { message: "second" }],
    } as unknown as ApiResult);

    // WHEN
    const result = getNumberPoolDivisions(params);

    // THEN
    await expect(result).rejects.toThrow("first; second");
  });
});
