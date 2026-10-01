import { beforeEach, describe, expect, test, vi } from "vitest";

import { getRepositoryCommitsFromApi } from "@/entities/repository/api/get-repository-commits-from-api";
import { getRepositoryCommits } from "@/entities/repository/domain/use-cases/get-repository-commits";

import {
  BEHIND_HEAD,
  fullHash,
  generateBehindCommitsResponse,
} from "../../../../../tests/fake/repository-commit";

vi.mock("@/entities/repository/api/get-repository-commits-from-api");

type ApiResponse = Awaited<ReturnType<typeof getRepositoryCommitsFromApi>>;

const PARAMS = { repositoryId: "repo-1", branchName: "main", limit: 20, offset: 0 };

describe("getRepositoryCommits", () => {
  const apiMock = vi.mocked(getRepositoryCommitsFromApi);

  beforeEach(() => {
    apiMock.mockReset();
  });

  test("returns the mapped log", async () => {
    // GIVEN
    apiMock.mockResolvedValueOnce({
      data: { InfrahubRepositoryCommits: generateBehindCommitsResponse() },
    } as ApiResponse);

    // WHEN
    const log = await getRepositoryCommits(PARAMS);

    // THEN
    expect(apiMock).toHaveBeenCalledWith(PARAMS);
    expect(log.commits[0]?.hash).toBe(fullHash(BEHIND_HEAD));
  });

  test("throws with every message when the response carries errors", async () => {
    // GIVEN
    apiMock.mockResolvedValueOnce({
      data: null,
      errors: [{ message: "No worker answered" }, { message: "Retry in 30 seconds" }],
    } as unknown as ApiResponse);

    // WHEN
    const read = getRepositoryCommits(PARAMS);

    // THEN
    await expect(read).rejects.toThrow("No worker answered; Retry in 30 seconds");
  });

  test("throws when the response carries neither data nor errors", async () => {
    // GIVEN
    apiMock.mockResolvedValueOnce({ data: null } as unknown as ApiResponse);

    // WHEN
    const read = getRepositoryCommits(PARAMS);

    // THEN
    await expect(read).rejects.toThrow("The commit log response carried no data");
  });
});
