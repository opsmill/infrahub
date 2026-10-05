import { describe, expect, test } from "vitest";

import { mapToRepositoryCommitLog } from "@/entities/repository/api/repository-commits.mappers";
import { RepositoryGitCondition } from "@/entities/repository/domain/model/repository";

import {
  BEHIND_HEAD,
  BEHIND_IMPORTED,
  fullHash,
  generateBehindCommitsResponse,
  generateNotClonedCommitsResponse,
  NOT_CLONED_MESSAGE,
} from "../../../../tests/fake/repository-commit";

describe("mapToRepositoryCommitLog", () => {
  test("keeps the wire fields and flattens the edges into commits", () => {
    // GIVEN
    const response = generateBehindCommitsResponse();

    // WHEN
    const log = mapToRepositoryCommitLog(response);

    // THEN
    expect(log.condition).toBe(RepositoryGitCondition.BEHIND);
    expect(log.imported_commit).toBe(fullHash(BEHIND_IMPORTED));
    expect(log.pending_count).toBe(2);
    expect(log.commits).toHaveLength(response.edges.length);
    expect(log.commits[0]).toEqual({
      hash: fullHash(BEHIND_HEAD),
      short_hash: BEHIND_HEAD,
      summary: "Bump firmware baseline",
      author_name: "Grace Hopper",
      authored_at: "2025-03-10T10:00:00Z",
      state: "HEAD",
    });
  });

  test("keeps the unavailable reason and a missing fetch time", () => {
    // GIVEN
    const response = generateNotClonedCommitsResponse();

    // WHEN
    const log = mapToRepositoryCommitLog(response);

    // THEN
    expect(log.fetched_at).toBeNull();
    expect(log.unavailable).toEqual({ reason: "NOT_CLONED", message: NOT_CLONED_MESSAGE });
    expect(log.commits).toEqual([]);
  });

  test("rejects a non-string commit timestamp instead of rendering it", () => {
    // GIVEN
    const response = generateBehindCommitsResponse();
    response.edges = response.edges.map((edge, index) =>
      index === 0 ? { node: { ...edge.node, authored_at: 42 } } : edge
    );

    // WHEN
    const map = () => mapToRepositoryCommitLog(response);

    // THEN
    expect(map).toThrow("Expected an ISO 8601 DateTime string");
  });

  test("reads a pending count left out of a later page as unknown", () => {
    // GIVEN
    const response = { ...generateBehindCommitsResponse(), pending_count: undefined };

    // WHEN
    const log = mapToRepositoryCommitLog(response);

    // THEN
    expect(log.pending_count).toBeNull();
  });
});
