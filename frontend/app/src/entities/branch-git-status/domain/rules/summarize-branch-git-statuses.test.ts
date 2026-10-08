import { describe, expect, it } from "vitest";

import type { BranchGitStatus } from "@/entities/branch-git-status/domain/model/branch-git-status";
import {
  type RepositoryListFetch,
  type RepositoryStatusFetch,
  summarizeBranchGitStatuses,
} from "@/entities/branch-git-status/domain/rules/summarize-branch-git-statuses";
import type { BranchRepositorySyncStatus } from "@/entities/repository/domain/model/branch-repository";

import {
  generateBranchGitRepository,
  generateRepositoryBranchStatus,
} from "../../../../../tests/fake/branch-git-status";
import { SYNC_STATUS } from "../../../../../tests/fake/branch-repositories";

const UNKNOWN: BranchRepositorySyncStatus = {
  value: "unknown",
  label: "Unknown",
  color: "#9ca3af",
  description: null,
};

const repository = (name: string) => generateBranchGitRepository({ id: `id-${name}`, name });

const row = (
  branchName: string,
  syncStatus = SYNC_STATUS.inSync,
  commit = `${branchName}-commit`
) => generateRepositoryBranchStatus({ branchName, syncStatus, commit });

const loaded = (
  name: string,
  rows: ReturnType<typeof row>[],
  count = rows.length
): RepositoryStatusFetch => ({ status: "ok", repository: repository(name), rows, count });

const listOf = (...statuses: RepositoryStatusFetch[]): RepositoryListFetch => ({
  status: "ok",
  statuses,
});

const summarize = (branchNames: string[], list: RepositoryListFetch) =>
  summarizeBranchGitStatuses(branchNames, list, UNKNOWN);

const repositoryNames = (status: BranchGitStatus | undefined) =>
  status?.status === "ok" ? status.repositories.map(({ repository }) => repository.name) : null;

describe("summarizeBranchGitStatuses", () => {
  it.each([
    { status: "pending" },
    { status: "denied" },
    { status: "error", message: "Repository list unavailable" },
  ] satisfies RepositoryListFetch[])(
    "gives every branch the repository list's $status state",
    (list) => {
      expect(summarize(["main", "feature"], list)).toEqual({ main: list, feature: list });
    }
  );

  it("marks every branch denied when every status read is denied", () => {
    // GIVEN
    const list = listOf(
      { status: "denied", repository: repository("a") },
      { status: "denied", repository: repository("b") }
    );

    // WHEN
    const statuses = summarize(["main", "feature"], list);

    // THEN
    expect(statuses).toEqual({ main: { status: "denied" }, feature: { status: "denied" } });
  });

  it("gives every branch an empty ok status when there are no repositories", () => {
    expect(summarize(["main"], listOf())).toEqual({
      main: { status: "ok", repositories: [], counts: [], unloaded: [] },
    });
  });

  it("shows the loaded repositories and carries a failed or denied one on every branch", () => {
    // GIVEN
    const failed = {
      status: "error" as const,
      repository: repository("broken"),
      message: "Repository index unavailable",
    };
    const denied = { status: "denied" as const, repository: repository("secret") };
    const list = listOf(loaded("visible", [row("main")]), failed, denied);

    // WHEN
    const statuses = summarize(["main", "feature"], list);

    // THEN
    expect(statuses.main).toMatchObject({
      status: "ok",
      repositories: [{ repository: { name: "visible" } }],
      unloaded: [failed, denied],
    });
    expect(statuses.feature).toEqual({
      status: "ok",
      repositories: [],
      counts: [],
      unloaded: [failed, denied],
    });
  });

  it("shows the loaded repositories while another repository's status is pending", () => {
    // GIVEN
    const pending = { status: "pending" as const, repository: repository("slow") };

    // WHEN
    const statuses = summarize(["main"], listOf(loaded("fast", [row("main")]), pending));

    // THEN
    expect(statuses.main).toMatchObject({
      status: "ok",
      repositories: [{ repository: { name: "fast" } }],
      unloaded: [pending],
    });
  });

  it("groups rows by branch name, worst first with ties by repository name", () => {
    // GIVEN
    const list = listOf(
      loaded("Zeta", [row("main"), row("feature", SYNC_STATUS.importError)]),
      loaded("alpha", [row("main", SYNC_STATUS.importError), row("feature")]),
      loaded("beta", [row("main", SYNC_STATUS.importError)]),
      loaded("gamma", [row("main", SYNC_STATUS.unknown)])
    );

    // WHEN
    const statuses = summarize(["main", "feature"], list);

    // THEN
    expect(repositoryNames(statuses.main)).toEqual(["alpha", "beta", "gamma", "Zeta"]);
    expect(repositoryNames(statuses.feature)).toEqual(["Zeta", "alpha"]);
  });

  it("keeps each row's commit and sync status on its repository state", () => {
    const statuses = summarize(
      ["feature"],
      listOf(loaded("alpha", [row("feature", SYNC_STATUS.importError, "abc")]))
    );

    expect(statuses.feature).toMatchObject({
      status: "ok",
      repositories: [
        { repository: { id: "id-alpha" }, commit: "abc", syncStatus: SYNC_STATUS.importError },
      ],
    });
  });

  it("counts repositories per sync status in the order of the repositories", () => {
    const statuses = summarize(
      ["main"],
      listOf(
        loaded("a", [row("main")]),
        loaded("b", [row("main", SYNC_STATUS.importError)]),
        loaded("c", [row("main")]),
        loaded("d", [generateRepositoryBranchStatus({ branchName: "main", syncStatus: null })]),
        loaded("e", [row("main", SYNC_STATUS.unknown)])
      )
    );

    expect(statuses.main).toMatchObject({
      counts: [
        { value: "error-import", label: "Import Error", count: 1 },
        { value: "unknown", label: "Unknown", count: 2 },
        { value: "in-sync", label: "In Sync", count: 2 },
      ],
    });
  });

  it("reads a row with no sync status as the unknown status it is given", () => {
    const statuses = summarize(
      ["main"],
      listOf(
        loaded("a", [generateRepositoryBranchStatus({ branchName: "main", syncStatus: null })])
      )
    );

    expect(statuses.main).toMatchObject({ repositories: [{ syncStatus: UNKNOWN }] });
  });

  it("reports an error for a branch absent from the pages the backend cut short", () => {
    // GIVEN two repositories with more branches than their page returned
    const list = listOf(
      loaded("a", [row("main")], 501),
      loaded("b", [row("main")], 501),
      loaded("c", [row("main"), row("feature")])
    );

    // WHEN
    const statuses = summarize(["main", "feature"], list);

    // THEN
    expect(statuses.main).toMatchObject({ status: "ok" });
    expect(statuses.feature).toEqual({
      status: "error",
      message:
        "Too many branches to load for a, b, so this branch could not be checked. Open the branch for the full list.",
    });
  });

  it("gives a branch with no rows an empty ok status", () => {
    const statuses = summarize(["local"], listOf(loaded("a", [row("main")])));

    expect(statuses.local).toEqual({ status: "ok", repositories: [], counts: [], unloaded: [] });
  });
});
