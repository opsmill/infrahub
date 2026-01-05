import { NetworkStatus } from "@apollo/client";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getBranchTaskStatusFromApi } from "@/entities/tasks/api/get-branch-task-status-from-api";

import { isTaskRunningOnBranch } from "./is-task-running-on-branch";

vi.mock("@/entities/tasks/api/get-branch-task-status-from-api");

describe("isTaskRunningOnBranch", () => {
  const mockGetBranchTaskStatus = vi.mocked(getBranchTaskStatusFromApi);

  beforeEach(() => {
    mockGetBranchTaskStatus.mockClear();
  });

  it("returns true when branch has running tasks", async () => {
    // GIVEN
    mockGetBranchTaskStatus.mockResolvedValueOnce({
      data: {
        InfrahubTaskBranchStatus: {
          count: 1,
        },
      },
      loading: false,
      networkStatus: NetworkStatus.ready,
    });

    // WHEN
    const result = await isTaskRunningOnBranch("main");

    // THEN
    expect(result).toBe(true);
    expect(mockGetBranchTaskStatus).toHaveBeenCalledWith("main");
  });

  it("returns false when branch has no running tasks", async () => {
    // GIVEN
    mockGetBranchTaskStatus.mockResolvedValueOnce({
      data: {
        InfrahubTaskBranchStatus: {
          count: 0,
        },
      },
      loading: false,
      networkStatus: NetworkStatus.ready,
    });

    // WHEN
    const result = await isTaskRunningOnBranch("main");

    // THEN
    expect(result).toBe(false);
    expect(mockGetBranchTaskStatus).toHaveBeenCalledWith("main");
  });

  it("returns false when branch status response is null", async () => {
    // GIVEN
    mockGetBranchTaskStatus.mockResolvedValueOnce({
      data: {
        InfrahubTaskBranchStatus: null,
      },
      loading: false,
      networkStatus: NetworkStatus.error,
    });

    // WHEN
    const result = await isTaskRunningOnBranch("main");

    // THEN
    expect(result).toBe(false);
    expect(mockGetBranchTaskStatus).toHaveBeenCalledWith("main");
  });
});
