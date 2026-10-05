import { describe, expect, it } from "vitest";

import { isRepositorySyncing } from "@/entities/repository/domain/rules/is-repository-syncing";

import {
  generateBranchRepository,
  SYNC_STATUS,
} from "../../../../../tests/fake/branch-repositories";

describe("isRepositorySyncing", () => {
  it("is true while the repository's sync status is syncing", () => {
    expect(isRepositorySyncing(generateBranchRepository({ syncStatus: SYNC_STATUS.syncing }))).toBe(
      true
    );
  });

  it("is false for any other sync status", () => {
    expect(isRepositorySyncing(generateBranchRepository())).toBe(false);
  });
});
