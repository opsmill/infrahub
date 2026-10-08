import { describe, expect, it } from "vitest";

import type { BranchGitRepository } from "@/entities/branch-git-status/domain/model/branch-git-repository";
import type { BranchRepositoryState } from "@/entities/branch-git-status/domain/model/branch-git-status";
import {
  formatFailedRepositoryCount,
  formatFailedRepositoryReasons,
  formatRepositoryState,
  formatSyncStatusCounts,
} from "@/entities/branch-git-status/domain/rules/format-branch-git-status";

const repository = (name: string): BranchGitRepository => ({
  id: `repo-${name}`,
  name,
  kind: "CoreRepository",
  isReadOnly: false,
});

const state = (overrides: Partial<BranchRepositoryState> = {}): BranchRepositoryState => ({
  repository: repository("repo-one"),
  commit: "1234567890abcdef",
  syncStatus: { value: "error-import", label: "Import Error", color: null, description: null },
  ...overrides,
});

describe("formatRepositoryState", () => {
  it("joins the label, the 7-character commit and read-only", () => {
    // GIVEN
    const readOnly = state({
      repository: { id: "r", name: "r", kind: "CoreReadOnlyRepository", isReadOnly: true },
    });

    // WHEN
    const text = formatRepositoryState(readOnly);

    // THEN
    expect(text).toBe("Import Error · 1234567 · read-only");
  });

  it("shows only the status for a read/write repository without a commit", () => {
    expect(formatRepositoryState(state({ commit: null }))).toBe("Import Error");
  });

  it("falls back to the raw value when the status has no label", () => {
    const text = formatRepositoryState(
      state({ syncStatus: { value: "mystery", label: null, color: null, description: null } })
    );

    expect(text).toBe("mystery · 1234567");
  });

  it("is empty when no part is present", () => {
    const text = formatRepositoryState(
      state({
        commit: null,
        syncStatus: { value: null, label: null, color: null, description: null },
      })
    );

    expect(text).toBe("");
  });
});

describe("formatSyncStatusCounts", () => {
  it("lists each label with its count", () => {
    const text = formatSyncStatusCounts([
      { value: "error-import", label: "Import Error", count: 1 },
      { value: "in-sync", label: "In Sync", count: 2 },
    ]);

    expect(text).toBe("Import Error: 1 · In Sync: 2");
  });
});

describe("formatFailedRepositoryCount", () => {
  it.each([
    { count: 1, text: "1 repository could not be loaded" },
    { count: 2, text: "2 repositories could not be loaded" },
  ])("reads $text", ({ count, text }) => {
    expect(formatFailedRepositoryCount(count)).toBe(text);
  });
});

describe("formatFailedRepositoryReasons", () => {
  it("names each repository with the reason it could not be loaded", () => {
    const text = formatFailedRepositoryReasons([
      { status: "denied", repository: repository("secrets") },
      {
        status: "error",
        repository: repository("broken"),
        message: "Repository index unavailable",
      },
    ]);

    expect(text).toBe("secrets: No permission · broken: Repository index unavailable");
  });
});
