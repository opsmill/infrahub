import { describe, expect, test } from "vitest";

import {
  READONLY_REPOSITORY_KIND,
  REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";
import { isShowingTrunkHistory } from "@/entities/repository/domain/rules/is-showing-trunk-history";

describe("isShowingTrunkHistory", () => {
  test("is true for a read-write repository on a branch that does not sync with Git", () => {
    // WHEN
    const result = isShowingTrunkHistory({
      repositoryKind: REPOSITORY_KIND,
      branch: { is_default: false, sync_with_git: false },
    });

    // THEN
    expect(result).toBe(true);
  });

  test.each([
    {
      case: "a read-only repository",
      repositoryKind: READONLY_REPOSITORY_KIND,
      branch: { is_default: false, sync_with_git: false },
    },
    {
      case: "a branch that syncs with Git",
      repositoryKind: REPOSITORY_KIND,
      branch: { is_default: false, sync_with_git: true },
    },
    {
      case: "a branch whose sync setting is unknown",
      repositoryKind: REPOSITORY_KIND,
      branch: { is_default: false, sync_with_git: null },
    },
    {
      case: "the default branch",
      repositoryKind: REPOSITORY_KIND,
      branch: { is_default: true, sync_with_git: false },
    },
  ])("is false for $case", ({ repositoryKind, branch }) => {
    // WHEN
    const result = isShowingTrunkHistory({ repositoryKind, branch });

    // THEN
    expect(result).toBe(false);
  });
});
