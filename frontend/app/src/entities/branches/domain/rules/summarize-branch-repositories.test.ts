import { describe, expect, it } from "vitest";

import { mapRepositoryBranchStatusRow } from "@/entities/repository/domain/model/repository-branch-status";

import { generateBranch } from "../../../../../tests/fake/branch";
import { generateDropdown } from "../../../../../tests/fake/dropdown";
import { generateRepositoryBranchStatus } from "../../../../../tests/fake/repository";
import {
  type RepositoryStatusFetch,
  summarizeBranchRepositories,
} from "./summarize-branch-repositories";

const IMPORT_ERROR = generateDropdown({ value: "error-import", label: "Import Error" });
const IN_SYNC = generateDropdown({ value: "in-sync", label: "In Sync" });
const UNKNOWN = generateDropdown({ value: "unknown", label: "Unknown" });

const main = generateBranch({ id: "b-main", name: "main", is_default: true, sync_with_git: true });
const feature = generateBranch({ id: "b-feature", name: "feature", sync_with_git: true });
const local = generateBranch({ id: "b-local", name: "local", sync_with_git: false });

const row = (name: string, syncStatus = IN_SYNC, commit = `${name}-commit`) =>
  mapRepositoryBranchStatusRow(
    generateRepositoryBranchStatus({
      name: { value: name },
      sync_status: syncStatus,
      commit: { value: commit },
    })
  );

const fetched = (
  name: string,
  rows: ReturnType<typeof row>[],
  isReadOnly = false,
  count = rows.length
): RepositoryStatusFetch => ({
  status: "ok",
  repository: {
    id: `id-${name}`,
    name,
    kind: isReadOnly ? "CoreReadOnlyRepository" : "CoreRepository",
    isReadOnly,
  },
  rows,
  count,
});

describe("summarizeBranchRepositories", () => {
  it("marks every branch denied when any repository is denied", () => {
    // GIVEN
    const fetches: RepositoryStatusFetch[] = [
      { status: "pending" },
      { status: "error", message: "boom" },
      { status: "denied" },
    ];

    // WHEN
    const summaries = summarizeBranchRepositories([main, feature], fetches);

    // THEN
    expect(summaries).toEqual({ main: { status: "denied" }, feature: { status: "denied" } });
  });

  it("marks every branch pending over an error", () => {
    const summaries = summarizeBranchRepositories(
      [main],
      [{ status: "error", message: "boom" }, { status: "pending" }]
    );

    expect(summaries).toEqual({ main: { status: "pending" } });
  });

  it("carries the first error's message to every branch", () => {
    const summaries = summarizeBranchRepositories(
      [main, feature],
      [
        fetched("a", [row("main")]),
        { status: "error", message: "first" },
        { status: "error", message: "second" },
      ]
    );

    expect(summaries.main).toEqual({ status: "error", message: "first" });
    expect(summaries.feature).toEqual({ status: "error", message: "first" });
  });

  it("groups rows by branch name, worst first with ties by repository name", () => {
    // GIVEN
    const fetches = [
      fetched("Zeta", [row("main"), row("feature", IMPORT_ERROR)]),
      fetched("alpha", [row("main", IMPORT_ERROR), row("feature")]),
      fetched("beta", [row("main", IMPORT_ERROR)]),
      fetched("gamma", [row("main", UNKNOWN)]),
    ];

    // WHEN
    const summaries = summarizeBranchRepositories([main, feature], fetches);

    // THEN
    const names = (name: string) => {
      const summary = summaries[name];
      return summary?.status === "ok" ? summary.repositories.map((s) => s.repository.name) : null;
    };
    expect(names("main")).toEqual(["alpha", "beta", "gamma", "Zeta"]);
    expect(names("feature")).toEqual(["Zeta", "alpha"]);
  });

  it("keeps each row's commit and sync status on its repository state", () => {
    const summaries = summarizeBranchRepositories(
      [feature],
      [fetched("alpha", [row("feature", IMPORT_ERROR, "abc")])]
    );

    expect(summaries.feature).toMatchObject({
      status: "ok",
      repositories: [{ repository: { id: "id-alpha" }, commit: "abc", syncStatus: IMPORT_ERROR }],
    });
  });

  it("counts repositories per sync status in worst-first order", () => {
    const summaries = summarizeBranchRepositories(
      [main],
      [
        fetched("a", [row("main")]),
        fetched("b", [row("main", IMPORT_ERROR)]),
        fetched("c", [row("main")]),
        fetched("d", [
          mapRepositoryBranchStatusRow(
            generateRepositoryBranchStatus({ name: { value: "main" }, sync_status: null })
          ),
        ]),
      ]
    );

    expect(summaries.main).toMatchObject({
      counts: [
        { value: "error-import", label: "Import Error", count: 1 },
        { value: null, label: "Unknown", count: 1 },
        { value: "in-sync", label: "In Sync", count: 2 },
      ],
    });
  });

  it("reports an error for a branch absent from a page the backend cut short", () => {
    // GIVEN a repository with more branches than the page returned
    const fetches = [
      fetched("a", [row("main")], false, 501),
      fetched("b", [row("main"), row("local")]),
    ];

    // WHEN
    const summaries = summarizeBranchRepositories([main, local], fetches);

    // THEN the branch on the page is summarised, the one past the cut is not guessed
    expect(summaries.main).toMatchObject({ status: "ok" });
    expect(summaries.local).toMatchObject({
      status: "error",
      message: expect.stringContaining("first 1 branches"),
    });
  });

  it("gives a branch with no rows an empty ok summary", () => {
    const summaries = summarizeBranchRepositories([local], [fetched("a", [row("main")])]);

    expect(summaries.local).toEqual({ status: "ok", repositories: [], counts: [] });
  });

  it("lists a read-only repository on an unsynced branch while a read/write one is absent", () => {
    // GIVEN the rows as the backend returns them: read/write lists only synced branches
    const fetches = [
      fetched("read-write", [row("main"), row("feature")]),
      fetched("read-only", [row("main"), row("feature"), row("local")], true),
    ];

    // WHEN
    const summaries = summarizeBranchRepositories([main, feature, local], fetches);

    // THEN
    expect(summaries.local).toMatchObject({
      status: "ok",
      repositories: [{ repository: { name: "read-only", isReadOnly: true } }],
    });
    expect(summaries.feature).toMatchObject({
      repositories: [{ repository: { name: "read-only" } }, { repository: { name: "read-write" } }],
    });
  });
});
