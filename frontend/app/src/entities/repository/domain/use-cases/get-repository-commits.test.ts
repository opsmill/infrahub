import { beforeEach, describe, expect, test, vi } from "vitest";

import { getRepositoryCommitsFromApi } from "@/entities/repository/api/get-repository-commits-from-api";
import {
  RepositoryGitCondition,
  RepositoryGitUnavailableReason,
} from "@/entities/repository/domain/model/repository";
import { RepositoryGitUnavailableError } from "@/entities/repository/domain/model/repository-git-unavailable-error";
import { getRepositoryCommits } from "@/entities/repository/domain/use-cases/get-repository-commits";

import {
  BEHIND_HEAD,
  fullHash,
  generateBehindCommitsResponse,
  generateNotClonedCommitsResponse,
  generateRepositoryCommitsResponse,
  NOT_CLONED_MESSAGE,
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

  test("throws the unavailable answer as a typed error that keeps the whole log", async () => {
    // GIVEN
    apiMock.mockResolvedValueOnce({
      data: { InfrahubRepositoryCommits: generateNotClonedCommitsResponse() },
    } as ApiResponse);

    // WHEN
    const read = getRepositoryCommits(PARAMS);

    // THEN
    const error = await read.catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(RepositoryGitUnavailableError);
    expect(error).toMatchObject({
      name: "RepositoryGitUnavailableError",
      message: NOT_CLONED_MESSAGE,
      reason: RepositoryGitUnavailableReason.NOT_CLONED,
      log: { git_ref: "main", condition: RepositoryGitCondition.UNAVAILABLE },
    });
  });

  test("throws a typed error without a reason when the unavailable answer carries none", async () => {
    // GIVEN
    apiMock.mockResolvedValueOnce({
      data: {
        InfrahubRepositoryCommits: generateRepositoryCommitsResponse({
          condition: "UNAVAILABLE",
          unavailable: null,
        }),
      },
    } as ApiResponse);

    // WHEN
    const read = getRepositoryCommits(PARAMS);

    // THEN
    await expect(read).rejects.toMatchObject({ reason: null, message: "" });
  });

  test.each([
    RepositoryGitCondition.NOT_TRACKED,
    RepositoryGitCondition.NO_REMOTE,
    RepositoryGitCondition.BEHIND,
    RepositoryGitCondition.IN_SYNC,
    RepositoryGitCondition.REWRITTEN,
    RepositoryGitCondition.ORPHANED,
  ])("returns %s as an answer", async (condition) => {
    // GIVEN
    apiMock.mockResolvedValueOnce({
      data: { InfrahubRepositoryCommits: generateRepositoryCommitsResponse({ condition }) },
    } as ApiResponse);

    // WHEN
    const log = await getRepositoryCommits(PARAMS);

    // THEN
    expect(log.condition).toBe(condition);
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
