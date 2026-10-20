import { describe, expect, it } from "vitest";

import {
  isAnyRepositorySyncing,
  isRepositorySyncing,
} from "@/entities/repository/domain/rules/repository-syncing";

import {
  generateBranchRepository,
  generateBranchRepositoryHealth,
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

describe("isAnyRepositorySyncing", () => {
  it("is true while the server counts a syncing repository", () => {
    expect(isAnyRepositorySyncing(generateBranchRepositoryHealth({ syncingCount: 1 }))).toBe(true);
  });

  it("is false when none is syncing, or before the health has loaded", () => {
    expect(isAnyRepositorySyncing(generateBranchRepositoryHealth())).toBe(false);
    expect(isAnyRepositorySyncing(undefined)).toBe(false);
  });
});
