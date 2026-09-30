import { beforeEach, describe, expect, test, vi } from "vitest";

import { getRepositoryCommitsFromApi } from "@/entities/repository/api/get-repository-commits-from-api";
import { REPOSITORY_GIT_CONDITION } from "@/entities/repository/domain/model/repository";
import { getRepositoryCommits } from "@/entities/repository/domain/use-cases/get-repository-commits";

import {
  BEHIND_HEAD,
  BEHIND_IMPORTED,
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

  test("maps the wire log onto the domain shape", async () => {
    // GIVEN
    apiMock.mockResolvedValueOnce({
      data: { InfrahubRepositoryCommits: generateBehindCommitsResponse() },
    } as ApiResponse);

    // WHEN
    const log = await getRepositoryCommits(PARAMS);

    // THEN
    expect(log.condition).toBe(REPOSITORY_GIT_CONDITION.BEHIND);
    expect(log.importedCommit).toBe(fullHash(BEHIND_IMPORTED));
    expect(log.commits[0]).toMatchObject({
      id: fullHash(BEHIND_HEAD),
      hash: fullHash(BEHIND_HEAD),
      shortHash: BEHIND_HEAD,
    });
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

  test("rejects a non-string commit timestamp instead of rendering it", async () => {
    // GIVEN
    const response = generateBehindCommitsResponse();
    response.edges = response.edges.map((edge, index) =>
      index === 0 ? { node: { ...edge.node, authored_at: 42 as never } } : edge
    );
    apiMock.mockResolvedValueOnce({ data: { InfrahubRepositoryCommits: response } } as ApiResponse);

    // WHEN
    const read = getRepositoryCommits(PARAMS);

    // THEN
    await expect(read).rejects.toThrow("Expected an ISO 8601 DateTime string");
  });
});
