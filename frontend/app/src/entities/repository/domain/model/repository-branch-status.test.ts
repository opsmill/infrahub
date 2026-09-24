import { describe, expect, it } from "vitest";

import {
  mapRepositoryBranchStatusPage,
  mapRepositoryBranchStatusRow,
} from "@/entities/repository/domain/model/repository-branch-status";

import { generateDropdown } from "../../../../../tests/fake/dropdown";
import {
  generateReadOnlyRepositoryBranchStatus,
  generateRepositoryBranchStatus,
  generateRepositoryBranchStatusPage,
  generateSparseRepositoryBranchStatus,
} from "../../../../../tests/fake/repository";

describe("mapRepositoryBranchStatusRow", () => {
  it("synthesises the row id from the branch name", () => {
    const row = mapRepositoryBranchStatusRow(
      generateRepositoryBranchStatus({ name: { value: "feature-auth" } })
    );

    expect(row.id).toBe("feature-auth");
    expect(row.name).toBe("feature-auth");
  });

  it("maps every populated field", () => {
    const row = mapRepositoryBranchStatusRow(
      generateReadOnlyRepositoryBranchStatus({
        name: { value: "main" },
        commit: { value: "abc123" },
      })
    );

    expect(row).toMatchObject({
      isDefault: true,
      commit: "abc123",
      ref: "refs/tags/v1.4.2",
    });
    expect(row.syncStatus).toEqual(generateDropdown());
  });

  it("falls back to defaults when every nullable field is null", () => {
    const row = mapRepositoryBranchStatusRow(generateSparseRepositoryBranchStatus());

    expect(row).toMatchObject({
      isDefault: false,
      commit: null,
      syncStatus: null,
      ref: null,
    });
  });

  it("falls back to defaults when every nullable field is absent", () => {
    const row = mapRepositoryBranchStatusRow({ name: { value: "staging" } });

    expect(row).toMatchObject({
      isDefault: false,
      commit: null,
      syncStatus: null,
      ref: null,
    });
  });

  it("drops a dropdown carrying no value", () => {
    const row = mapRepositoryBranchStatusRow(
      generateRepositoryBranchStatus({ sync_status: generateDropdown({ value: null }) })
    );

    expect(row.syncStatus).toBeNull();
  });

  it("keeps the dropdown label and colour the payload supplied", () => {
    const row = mapRepositoryBranchStatusRow(
      generateRepositoryBranchStatus({
        sync_status: generateDropdown({
          value: "quarantined",
          label: "Quarantined",
          color: "#4c1d95",
        }),
      })
    );

    expect(row.syncStatus).toMatchObject({
      value: "quarantined",
      label: "Quarantined",
      color: "#4c1d95",
    });
  });
});

describe("mapRepositoryBranchStatusPage", () => {
  it("keeps the server count rather than the number of rows received", () => {
    const page = mapRepositoryBranchStatusPage(
      generateRepositoryBranchStatusPage({
        rows: [
          generateRepositoryBranchStatus({ name: { value: "main" } }),
          generateRepositoryBranchStatus({ name: { value: "staging" } }),
        ],
        count: 42,
      })
    );

    expect(page.count).toBe(42);
    expect(page.rows.map((row) => row.name)).toEqual(["main", "staging"]);
  });

  it("maps an empty page", () => {
    const page = mapRepositoryBranchStatusPage(generateRepositoryBranchStatusPage({ rows: [] }));

    expect(page).toEqual({ rows: [], count: 0 });
  });
});
