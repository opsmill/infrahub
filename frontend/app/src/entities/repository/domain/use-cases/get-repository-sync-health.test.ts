import { afterEach, describe, expect, it, vi } from "vitest";

import { getRepositorySyncCountsFromApi } from "@/entities/repository/api/get-repository-sync-counts-from-api";
import { getRepositorySyncHealth } from "@/entities/repository/domain/use-cases/get-repository-sync-health";

vi.mock("@/entities/repository/api/get-repository-sync-counts-from-api");

const getRepositorySyncCountsFromApiMock = vi.mocked(getRepositorySyncCountsFromApi);

type CountsResponse = Awaited<ReturnType<typeof getRepositorySyncCountsFromApi>>;

const mockCounts = ({ total, failing }: { total: number; failing: number }) => {
  getRepositorySyncCountsFromApiMock.mockResolvedValue({
    data: { total: { count: total }, failing: { count: failing } },
  } as unknown as CountsResponse);
};

describe("getRepositorySyncHealth", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("reports none when the branch has no repositories", async () => {
    // GIVEN
    mockCounts({ total: 0, failing: 0 });

    // WHEN
    const health = await getRepositorySyncHealth("branch1");

    // THEN
    expect(health).toBe("none");
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

  it("takes both counts from a single request", async () => {
    // GIVEN
    mockCounts({ total: 3, failing: 1 });

    // WHEN
    await getRepositorySyncHealth("branch1");

    // THEN
    expect(getRepositorySyncCountsFromApiMock).toHaveBeenCalledTimes(1);
  });

  it("asks about the given branch, at current state", async () => {
    // GIVEN
    mockCounts({ total: 3, failing: 0 });

    // WHEN
    await getRepositorySyncHealth("branch1");

    // THEN
    expect(getRepositorySyncCountsFromApiMock).toHaveBeenCalledWith({
      branchName: "branch1",
      atDate: null,
    });
  });

  it("raises the reported error rather than returning a verdict", async () => {
    // GIVEN
    getRepositorySyncCountsFromApiMock.mockResolvedValue({
      data: null,
      errors: [{ message: "boom" }],
    } as unknown as CountsResponse);

    // WHEN / THEN
    await expect(getRepositorySyncHealth("branch1")).rejects.toThrow("boom");
  });

  it("propagates a failed request rather than reporting health", async () => {
    // GIVEN
    getRepositorySyncCountsFromApiMock.mockRejectedValue(new Error("offline"));

    // WHEN / THEN
    await expect(getRepositorySyncHealth("branch1")).rejects.toThrow("offline");
  });
});
