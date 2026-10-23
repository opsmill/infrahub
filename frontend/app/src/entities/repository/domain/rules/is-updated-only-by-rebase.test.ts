import { describe, expect, test } from "vitest";

import {
  READONLY_REPOSITORY_KIND,
  REPOSITORY_INTERNAL_STATUS_STAGING,
  REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";
import { isUpdatedOnlyByRebase } from "@/entities/repository/domain/rules/is-updated-only-by-rebase";

const NON_SYNCED_BRANCH = { isDefaultBranch: false, syncWithGit: false };

describe("isUpdatedOnlyByRebase", () => {
  test("is true for an active read-write repository on a branch that does not sync with Git", () => {
    // WHEN
    const result = isUpdatedOnlyByRebase({
      repositoryKind: REPOSITORY_KIND,
      internalStatus: "active",
      ...NON_SYNCED_BRANCH,
    });

    // THEN
    expect(result).toBe(true);
  });

  test.each([
    {
      case: "a read-only repository",
      repositoryKind: READONLY_REPOSITORY_KIND,
      internalStatus: "active",
      ...NON_SYNCED_BRANCH,
    },
    {
      case: "a repository added on the branch",
      repositoryKind: REPOSITORY_KIND,
      internalStatus: REPOSITORY_INTERNAL_STATUS_STAGING,
      ...NON_SYNCED_BRANCH,
    },
    {
      case: "a branch that syncs with Git",
      repositoryKind: REPOSITORY_KIND,
      internalStatus: "active",
      isDefaultBranch: false,
      syncWithGit: true,
    },
    {
      case: "a branch whose sync setting is unknown",
      repositoryKind: REPOSITORY_KIND,
      internalStatus: "active",
      isDefaultBranch: false,
      syncWithGit: null,
    },
    {
      case: "the default branch",
      repositoryKind: REPOSITORY_KIND,
      internalStatus: "active",
      isDefaultBranch: true,
      syncWithGit: false,
    },
  ])("is false for $case", ({ repositoryKind, internalStatus, isDefaultBranch, syncWithGit }) => {
    // WHEN
    const result = isUpdatedOnlyByRebase({
      repositoryKind,
      internalStatus,
      isDefaultBranch,
      syncWithGit,
    });

    // THEN
    expect(result).toBe(false);
  });
});
