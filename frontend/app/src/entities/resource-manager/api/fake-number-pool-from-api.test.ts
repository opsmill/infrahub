import { describe, expect, it } from "vitest";

import {
  getFakeNumberPoolAllocationCount,
  getFakeNumberPoolAllocations,
  getFakeNumberPoolUtilization,
} from "./fake-number-pool-from-api";

const params = { poolId: "pool-id", branchName: "main", offset: 0, limit: 100 };

describe("getFakeNumberPoolUtilization", () => {
  it("counts as used exactly the numbers the allocations list", async () => {
    // GIVEN
    const { data: allocationCount } = await getFakeNumberPoolAllocationCount(params);

    // WHEN
    const { data } = await getFakeNumberPoolUtilization();

    // THEN
    expect(data.InfrahubNumberPoolUtilization.figures.used).toBe(
      allocationCount.InfrahubNumberPoolAllocations.count
    );
  });
});

describe("getFakeNumberPoolAllocations", () => {
  it("returns one page of the selected range", async () => {
    // WHEN
    const { data } = await getFakeNumberPoolAllocations({
      ...params,
      rangeId: "fake-range-1",
      offset: 400,
    });

    // THEN
    const { allocations } = data.InfrahubNumberPoolAllocations;
    expect(allocations.map(({ value }) => value)).toEqual(
      Array.from({ length: 12 }, (_, index) => 64_912 + index)
    );
  });

  it("refuses a range that is not in the pool", async () => {
    // WHEN
    const { errors } = await getFakeNumberPoolAllocations({ ...params, rangeId: "unknown" });

    // THEN
    expect(errors).toEqual([{ message: "The pool pool-id has no range unknown" }]);
  });
});

describe("getFakeNumberPoolAllocationCount", () => {
  it("counts the numbers of the selected range", async () => {
    // WHEN
    const { data } = await getFakeNumberPoolAllocationCount({
      ...params,
      rangeId: "fake-range-1",
    });

    // THEN
    expect(data.InfrahubNumberPoolAllocations.count).toBe(412);
  });

  it("refuses a range that is not in the pool", async () => {
    // WHEN
    const { errors } = await getFakeNumberPoolAllocationCount({ ...params, rangeId: "unknown" });

    // THEN
    expect(errors).toEqual([{ message: "The pool pool-id has no range unknown" }]);
  });
});
