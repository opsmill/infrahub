import { CombinedError } from "@urql/core";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createNumberPoolRangeFromApi } from "@/entities/resource-manager/api/create-number-pool-range-from-api";
import { deleteNumberPoolRangeFromApi } from "@/entities/resource-manager/api/delete-number-pool-range-from-api";
import { updateNumberPoolRangeFromApi } from "@/entities/resource-manager/api/update-number-pool-range-from-api";
import type { RangeChanges } from "@/entities/resource-manager/domain/model/number-pool-range";

import {
  applyNumberPoolRangeChanges,
  UNEXPECTED_RANGE_SAVE_ERROR,
} from "./apply-number-pool-range-changes";

vi.mock("@/entities/resource-manager/api/create-number-pool-range-from-api");
vi.mock("@/entities/resource-manager/api/update-number-pool-range-from-api");
vi.mock("@/entities/resource-manager/api/delete-number-pool-range-from-api");

const createMock = vi.mocked(createNumberPoolRangeFromApi);
const updateMock = vi.mocked(updateNumberPoolRangeFromApi);
const deleteMock = vi.mocked(deleteNumberPoolRangeFromApi);

const serverRefusal = (message: string) =>
  new Error(message, { cause: new CombinedError({ graphQLErrors: [{ message }] }) });

const changes: RangeChanges = {
  deletes: ["r-old"],
  smaller: [{ id: "r-1", start: 1n, end: 15n, weight: null }],
  larger: [{ id: "r-2", start: 16n, end: 30n, weight: 5 }],
  creates: [{ start: 100n, end: 200n, weight: null }],
};

describe("applyNumberPoolRangeChanges", () => {
  const calls: string[] = [];

  beforeEach(() => {
    vi.resetAllMocks();
    calls.length = 0;
    deleteMock.mockImplementation(async ({ id }) => {
      calls.push(`delete ${id}`);
      return { data: {} as never };
    });
    updateMock.mockImplementation(async ({ range }) => {
      calls.push(`update ${range.id}`);
      return { data: {} as never };
    });
    createMock.mockImplementation(async ({ range }) => {
      calls.push(`create ${range.start}`);
      return { data: {} as never };
    });
  });

  it("sends deletes, then smaller updates, then larger updates, then creates", async () => {
    // GIVEN one change of each group

    // WHEN the changes are applied
    const result = await applyNumberPoolRangeChanges({
      branchName: "main",
      poolId: "pool-1",
      changes,
    });

    // THEN the calls follow the safe order and all four are counted
    expect(calls).toEqual(["delete r-old", "update r-1", "update r-2", "create 100"]);
    expect(result).toEqual({ errorMessage: null });
    expect(createMock).toHaveBeenCalledWith({
      branchName: "main",
      poolId: "pool-1",
      range: { start: 100n, end: 200n, weight: null },
    });
    expect(updateMock).toHaveBeenCalledWith({
      branchName: "main",
      range: { id: "r-1", start: 1n, end: 15n, weight: null },
    });
    expect(deleteMock).toHaveBeenCalledWith({ branchName: "main", id: "r-old" });
  });

  it("sends nothing when there are no changes", async () => {
    // GIVEN no changes
    const empty: RangeChanges = { deletes: [], smaller: [], larger: [], creates: [] };

    // WHEN applied
    const result = await applyNumberPoolRangeChanges({
      branchName: "main",
      poolId: "pool-1",
      changes: empty,
    });

    // THEN no call is made
    expect(calls).toEqual([]);
    expect(result).toEqual({ errorMessage: null });
  });

  it("stops at the first server refusal and returns its message", async () => {
    // GIVEN the larger update is refused for an overlap
    updateMock.mockImplementation(async ({ range }) => {
      calls.push(`update ${range.id}`);
      if (range.id === "r-2") throw serverRefusal("Range 16-30 overlaps 25-40 (r-9)");
      return { data: {} as never };
    });

    // WHEN the changes are applied
    const result = await applyNumberPoolRangeChanges({
      branchName: "main",
      poolId: "pool-1",
      changes,
    });

    // THEN the create is never sent
    expect(calls).toEqual(["delete r-old", "update r-1", "update r-2"]);
    expect(createMock).not.toHaveBeenCalled();
    expect(result).toEqual({ errorMessage: "Range 16-30 overlaps 25-40 (r-9)" });
  });

  it("stops at a network failure and returns a generic message", async () => {
    // GIVEN the first delete fails before reaching the server
    deleteMock.mockRejectedValue(new TypeError("Failed to fetch"));

    // WHEN the changes are applied
    const result = await applyNumberPoolRangeChanges({
      branchName: "main",
      poolId: "pool-1",
      changes,
    });

    // THEN nothing else is sent and the generic message is returned
    expect(updateMock).not.toHaveBeenCalled();
    expect(createMock).not.toHaveBeenCalled();
    expect(result).toEqual({ errorMessage: UNEXPECTED_RANGE_SAVE_ERROR });
  });
});
