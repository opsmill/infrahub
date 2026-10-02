import { describe, expect, it } from "vitest";

import type { BranchRepositoryState } from "@/entities/branches/domain/model/branch-repository-summary";

import { formatRepositoryState, formatSyncStatusCounts } from "./format-repository-summary";

const state = (overrides: Partial<BranchRepositoryState> = {}): BranchRepositoryState => ({
  repository: { id: "repo-1", name: "repo-one", kind: "CoreRepository", isReadOnly: false },
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

  it("omits the commit and the read-only tag for a read/write repository", () => {
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
