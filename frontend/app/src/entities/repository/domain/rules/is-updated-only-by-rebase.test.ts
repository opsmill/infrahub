import { describe, expect, test } from "vitest";

import {
  READONLY_REPOSITORY_KIND,
  REPOSITORY_INTERNAL_STATUS_STAGING,
  REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";
import { isUpdatedOnlyByRebase } from "@/entities/repository/domain/rules/is-updated-only-by-rebase";

const NON_SYNCED_BRANCH = { is_default: false, sync_with_git: false };

describe("isUpdatedOnlyByRebase", () => {
  test("is true for an active read-write repository on a branch that does not sync with Git", () => {
    // WHEN
    const result = isUpdatedOnlyByRebase({
      repositoryKind: REPOSITORY_KIND,
      internalStatus: "active",
      branch: NON_SYNCED_BRANCH,
    });

    // THEN
    expect(result).toBe(true);
  });

  test.each([
    {
      case: "a read-only repository",
      repositoryKind: READONLY_REPOSITORY_KIND,
      internalStatus: "active",
      branch: NON_SYNCED_BRANCH,
    },
    {
      case: "a repository added on the branch",
      repositoryKind: REPOSITORY_KIND,
      internalStatus: REPOSITORY_INTERNAL_STATUS_STAGING,
      branch: NON_SYNCED_BRANCH,
    },
    {
      case: "a branch that syncs with Git",
      repositoryKind: REPOSITORY_KIND,
      internalStatus: "active",
      branch: { is_default: false, sync_with_git: true },
    },
    {
      case: "a branch whose sync setting is unknown",
      repositoryKind: REPOSITORY_KIND,
      internalStatus: "active",
      branch: { is_default: false, sync_with_git: null },
    },
    {
      case: "the default branch",
      repositoryKind: REPOSITORY_KIND,
      internalStatus: "active",
      branch: { is_default: true, sync_with_git: false },
    },
  ])("is false for $case", ({ repositoryKind, internalStatus, branch }) => {
    // WHEN
    const result = isUpdatedOnlyByRebase({ repositoryKind, internalStatus, branch });

    // THEN
    expect(result).toBe(false);
  });
});
