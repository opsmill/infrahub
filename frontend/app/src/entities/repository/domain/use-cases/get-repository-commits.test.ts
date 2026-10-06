import { beforeEach, describe, expect, test, vi } from "vitest";

import { getRepositoryCommitsFromApi } from "@/entities/repository/api/get-repository-commits-from-api";
import {
  RepositoryCommitState,
  RepositoryGitCondition,
  RepositoryGitUnavailableReason,
} from "@/entities/repository/domain/model/repository";
import { RepositoryGitUnavailableError } from "@/entities/repository/domain/model/repository-git-unavailable-error";
import { getRepositoryCommits } from "@/entities/repository/domain/use-cases/get-repository-commits";

import {
  BEHIND_HEAD,
  fullHash,
  generateBehindCommitsResponse,
  generateCommitsApiResult,
  generateRepositoryCommitNode,
  generateRepositoryCommitsResponse,
  NOT_CLONED_MESSAGE,
} from "../../../../../tests/fake/repository-commit";

vi.mock("@/entities/repository/api/get-repository-commits-from-api");

const PARAMS = { repositoryId: "repo-1", branchName: "main", limit: 20, offset: 0 };

describe("getRepositoryCommits", () => {
  const apiMock = vi.mocked(getRepositoryCommitsFromApi);

  beforeEach(() => {
    apiMock.mockReset();
  });

  test("returns the mapped log", async () => {
    // GIVEN
    apiMock.mockResolvedValueOnce(generateCommitsApiResult(generateBehindCommitsResponse()));

    // WHEN
    const log = await getRepositoryCommits(PARAMS);

    // THEN
    expect(apiMock).toHaveBeenCalledWith(PARAMS);
    expect(log.commits[0]?.hash).toBe(fullHash(BEHIND_HEAD));
  });

  test("throws the unavailable answer as a typed error that keeps the whole log", async () => {
    // GIVEN
    const remoteHead = fullHash("c0ffee1");
    const importedCommit = fullHash("dec0de2");
    apiMock.mockResolvedValueOnce(
      generateCommitsApiResult(
        generateRepositoryCommitsResponse({
          condition: "UNAVAILABLE",
          imported_commit: importedCommit,
          remote_head: remoteHead,
          pending_count: 1,
          fetched_at: "2025-03-10T12:00:00Z",
          checked_at: "2025-03-11T08:30:00Z",
          unavailable: { reason: "NOT_CLONED", message: NOT_CLONED_MESSAGE },
          edges: [{ node: generateRepositoryCommitNode({ short_hash: "c0ffee1", state: "HEAD" }) }],
        })
      )
    );

    // WHEN
    const read = getRepositoryCommits(PARAMS);

    // THEN
    const error = await read.catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(RepositoryGitUnavailableError);
    expect(error).toMatchObject({
      name: "RepositoryGitUnavailableError",
      message: NOT_CLONED_MESSAGE,
      reason: RepositoryGitUnavailableReason.NOT_CLONED,
    });
    expect(error).toHaveProperty("log", {
      repository_id: "repo-1",
      branch_name: "test-branch",
      git_ref: "main",
      condition: RepositoryGitCondition.UNAVAILABLE,
      imported_commit: importedCommit,
      remote_head: remoteHead,
      pending_count: 1,
      fetched_at: "2025-03-10T12:00:00Z",
      checked_at: "2025-03-11T08:30:00Z",
      unavailable: {
        reason: RepositoryGitUnavailableReason.NOT_CLONED,
        message: NOT_CLONED_MESSAGE,
      },
      commits: [
        {
          hash: remoteHead,
          short_hash: "c0ffee1",
          summary: "Add device inventory",
          author_name: "Ada Lovelace",
          authored_at: "2025-03-10T10:00:00Z",
          state: RepositoryCommitState.HEAD,
        },
      ],
    });
  });

  test("throws a typed error without a reason when the unavailable answer carries none", async () => {
    // GIVEN
    apiMock.mockResolvedValueOnce(
      generateCommitsApiResult(
        generateRepositoryCommitsResponse({
          condition: "UNAVAILABLE",
          unavailable: null,
        })
      )
    );

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
    apiMock.mockResolvedValueOnce(
      generateCommitsApiResult(generateRepositoryCommitsResponse({ condition }))
    );

    // WHEN
    const log = await getRepositoryCommits(PARAMS);

    // THEN
    expect(log.condition).toBe(condition);
  });

  test("throws with every message when the response carries errors", async () => {
    // GIVEN
    apiMock.mockResolvedValueOnce({
      // @ts-expect-error The client types data as always present, but a resolver error answers with null.
      data: null,
      errors: [{ message: "No worker answered" }, { message: "Retry in 30 seconds" }],
    });

    // WHEN
    const read = getRepositoryCommits(PARAMS);

    // THEN
    await expect(read).rejects.toThrow("No worker answered; Retry in 30 seconds");
  });

  test("throws when the response carries neither data nor errors", async () => {
    // GIVEN
    // @ts-expect-error The client types data as always present, but an empty response reaches this guard.
    apiMock.mockResolvedValueOnce({ data: null });

    // WHEN
    const read = getRepositoryCommits(PARAMS);

    // THEN
    await expect(read).rejects.toThrow("The commit log response carried no data");
  });
});
