import { describe, expect, test } from "vitest";

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
  test("synthesises the row id from the branch name", () => {
    const row = mapRepositoryBranchStatusRow(
      generateRepositoryBranchStatus({ name: { value: "feature-auth" } })
    );

    expect(row.id).toBe("feature-auth");
    expect(row.name).toBe("feature-auth");
  });

  test("maps every populated field", () => {
    const row = mapRepositoryBranchStatusRow(
      generateReadOnlyRepositoryBranchStatus({
        name: { value: "main" },
        status: { value: "OPEN" },
        commit: { value: "abc123" },
      })
    );

    expect(row).toMatchObject({
      status: "OPEN",
      isDefault: true,
      syncWithGit: true,
      branchedFrom: "2024-12-12T09:36:44.968813Z",
      commit: "abc123",
      ref: "refs/tags/v1.4.2",
    });
    expect(row.syncStatus).toEqual(generateDropdown());
  });

  test("falls back to defaults when every nullable field is null", () => {
    const row = mapRepositoryBranchStatusRow(generateSparseRepositoryBranchStatus());

    expect(row).toMatchObject({
      isDefault: false,
      syncWithGit: false,
      branchedFrom: null,
      commit: null,
      syncStatus: null,
      internalStatus: null,
      ref: null,
    });
  });

  test("falls back to defaults when every nullable field is absent", () => {
    const row = mapRepositoryBranchStatusRow({
      name: { value: "staging" },
      status: { value: "OPEN" },
    });

    expect(row).toMatchObject({
      isDefault: false,
      syncWithGit: false,
      branchedFrom: null,
      commit: null,
      syncStatus: null,
      internalStatus: null,
      ref: null,
    });
  });

  test("drops a dropdown carrying no value", () => {
    const row = mapRepositoryBranchStatusRow(
      generateRepositoryBranchStatus({
        sync_status: generateDropdown({ value: null }),
        internal_status: generateDropdown({ value: null }),
      })
    );

    expect(row.syncStatus).toBeNull();
    expect(row.internalStatus).toBeNull();
  });

  test("keeps the dropdown label and colour the payload supplied", () => {
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
  test("keeps the server count rather than the number of rows received", () => {
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

  test("maps an empty page", () => {
    const page = mapRepositoryBranchStatusPage(generateRepositoryBranchStatusPage({ rows: [] }));

    expect(page).toEqual({ rows: [], count: 0 });
  });
});
