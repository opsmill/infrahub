import { describe, expect, test } from "vitest";

import { RepositoryGitUnavailableReason } from "@/entities/repository/domain/model/repository";
import { shouldRetryGitUnavailable } from "@/entities/repository/domain/rules/should-retry-git-unavailable";

describe("shouldRetryGitUnavailable", () => {
  test("NOT_CLONED may resolve, so it is retried", () => {
    expect(shouldRetryGitUnavailable(RepositoryGitUnavailableReason.NOT_CLONED)).toBe(true);
  });

  test("NOT_IMPLEMENTED never resolves, so it is not retried", () => {
    expect(shouldRetryGitUnavailable(RepositoryGitUnavailableReason.NOT_IMPLEMENTED)).toBe(false);
  });

  test("a missing reason is still retried", () => {
    expect(shouldRetryGitUnavailable(null)).toBe(true);
  });
});
