import { afterEach, describe, expect, it, vi } from "vitest";

import { getObjectsCount } from "@/entities/nodes/object/domain/use-cases/get-objects-count";
import { REPOSITORY_ERROR_IMPORT_FILTER } from "@/entities/repository/domain/model/repository";
import { getRepositorySyncHealth } from "@/entities/repository/domain/use-cases/get-repository-sync-health";

vi.mock("@/entities/nodes/object/domain/use-cases/get-objects-count");

const getObjectsCountMock = vi.mocked(getObjectsCount);

/** The two counts are told apart by their filter, never by call order. */
const mockCounts = ({ total, failing }: { total: number; failing?: number }) => {
  getObjectsCountMock.mockImplementation(async ({ filters }) => {
    const isFailingLookup = filters?.some(
      (filter) => filter.name === REPOSITORY_ERROR_IMPORT_FILTER.name
    );
    return isFailingLookup ? (failing ?? 0) : total;
  });
};

describe("getRepositorySyncHealth", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("reports none when the branch has no repositories", async () => {
    // GIVEN
    mockCounts({ total: 0 });

    // WHEN
    const health = await getRepositorySyncHealth("branch1");

    // THEN
    expect(health).toBe("none");
  });

  it("does not ask for the failing count when there are no repositories", async () => {
    // GIVEN
    mockCounts({ total: 0 });

    // WHEN
    await getRepositorySyncHealth("branch1");

    // THEN none failing follows from none at all, so the second request is never issued
    expect(getObjectsCountMock).toHaveBeenCalledTimes(1);
  });

  it("reports failing when at least one repository carries the import error", async () => {
    // GIVEN
    mockCounts({ total: 3, failing: 1 });

    // WHEN
    const health = await getRepositorySyncHealth("branch1");

    // THEN
    expect(health).toBe("failing");
  });

  it("reports in-sync when repositories exist and none are failing", async () => {
    // GIVEN
    mockCounts({ total: 3, failing: 0 });

    // WHEN
    const health = await getRepositorySyncHealth("branch1");

    // THEN
    expect(health).toBe("in-sync");
  });

  it("asks about the given branch, at current state", async () => {
    // GIVEN
    mockCounts({ total: 3, failing: 0 });

    // WHEN
    await getRepositorySyncHealth("branch1");

    // THEN
    expect(getObjectsCountMock).toHaveBeenCalledTimes(2);
    for (const call of getObjectsCountMock.mock.calls) {
      expect(call[0].branchName).toBe("branch1");
      expect(call[0].atDate).toBeNull();
    }
  });

  it("propagates a failed lookup rather than reporting health", async () => {
    // GIVEN
    getObjectsCountMock.mockRejectedValue(new Error("boom"));

    // WHEN / THEN
    await expect(getRepositorySyncHealth("branch1")).rejects.toThrow("boom");
  });
});
