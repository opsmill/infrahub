import { beforeEach, describe, expect, test, vi } from "vitest";

import { getRepositoryCommitStatusFromApi } from "@/entities/repository/api/get-repository-commit-status-from-api";
import { getRepositoryCommitStatus } from "@/entities/repository/domain/use-cases/get-repository-commit-status";

vi.mock("@/entities/repository/api/get-repository-commit-status-from-api");

type ApiResponse = Awaited<ReturnType<typeof getRepositoryCommitStatusFromApi>>;

const PARAMS = { repositoryId: "repo-1", branchName: "main" };

describe("getRepositoryCommitStatus", () => {
  const apiMock = vi.mocked(getRepositoryCommitStatusFromApi);

  beforeEach(() => {
    apiMock.mockReset();
  });

  test("returns the condition and pending count", async () => {
    // GIVEN
    apiMock.mockResolvedValueOnce({
      data: { InfrahubRepositoryCommits: { condition: "BEHIND", pending_count: 2 } },
    } as ApiResponse);

    // WHEN
    const status = await getRepositoryCommitStatus(PARAMS);

    // THEN
    expect(apiMock).toHaveBeenCalledWith(PARAMS);
    expect(status).toEqual({ condition: "BEHIND", pending_count: 2 });
  });

  test("throws with every message when the response carries errors", async () => {
    // GIVEN
    apiMock.mockResolvedValueOnce({
      data: null,
      errors: [{ message: "No worker answered" }, { message: "Retry in 30 seconds" }],
    } as unknown as ApiResponse);

    // WHEN
    const read = getRepositoryCommitStatus(PARAMS);

    // THEN
    await expect(read).rejects.toThrow("No worker answered; Retry in 30 seconds");
  });

  test("throws when the response carries neither data nor errors", async () => {
    // GIVEN
    apiMock.mockResolvedValueOnce({ data: null } as unknown as ApiResponse);

    // WHEN
    const read = getRepositoryCommitStatus(PARAMS);

    // THEN
    await expect(read).rejects.toThrow("The commit log response carried no status");
  });
});
