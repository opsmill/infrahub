import { describe, expect, it } from "vitest";

import type { BranchRepositoriesFetch } from "@/entities/branches/domain/model/branch-table-row";
import { toBranchTableRows } from "@/entities/branches/domain/rules/to-branch-table-rows";
import { READONLY_REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";
import { rankRepositories } from "@/entities/repository/domain/rules/rank-repositories";

import { generateBranch } from "../../../../../tests/fake/branch";
import {
  generateBranchRepositoriesResult,
  generateBranchRepository,
  OPERATIONAL_STATUS,
  SYNC_STATUS,
} from "../../../../../tests/fake/branch-repositories";

const main = generateBranch({ id: "branch-main", name: "main", is_default: true });
const feature = generateBranch({ id: "branch-feature", name: "feature" });

const toRows = (branches = [main], entries: Array<[string, BranchRepositoriesFetch]> = []) =>
  toBranchTableRows({
    branches,
    fetchByBranchId: new Map(entries),
    orderRepositories: rankRepositories,
  });

const alpha = generateBranchRepository({ id: "repo-alpha", name: "alpha" });
const bravo = generateBranchRepository({ id: "repo-bravo", name: "Bravo" });
const broken = generateBranchRepository({
  id: "repo-broken",
  name: "zulu",
  syncStatus: SYNC_STATUS.importError,
});
const unreachable = generateBranchRepository({
  id: "repo-unreachable",
  name: "yankee",
  operationalStatus: OPERATIONAL_STATUS.errorCred,
});
const charlie = generateBranchRepository({ id: "repo-charlie", name: "charlie" });

const denied: BranchRepositoriesFetch = { status: "denied" };
const failed: BranchRepositoriesFetch = { status: "error", message: "Server exploded" };
const pending: BranchRepositoriesFetch = { status: "pending" };

describe("toBranchTableRows", () => {
  it("gives one row per repository, anchored on the branch id", () => {
    // GIVEN a branch with three repositories
    const fetch = generateBranchRepositoriesResult([alpha, bravo, charlie]);

    // WHEN rows are built
    const rows = toRows([main], [[main.id, fetch]]);

    // THEN there is one ok row per repository with unique, anchor-first ids
    expect(rows.map((row) => row.id)).toEqual([
      main.id,
      `${main.id}:${bravo.id}`,
      `${main.id}:${charlie.id}`,
    ]);
    expect(rows.map((row) => row.repository)).toEqual([alpha, bravo, charlie]);
    expect(rows.map((row) => row.state)).toEqual(["ok", "ok", "ok"]);
    expect(new Set(rows.map((row) => row.id)).size).toBe(3);
  });

  it("orders import errors first, then unreachable, then by name case-insensitively", () => {
    const fetch = generateBranchRepositoriesResult([charlie, bravo, broken, unreachable, alpha]);

    const rows = toRows([main], [[main.id, fetch]]);

    expect(rows.map((row) => row.repository?.name)).toEqual([
      "zulu",
      "yankee",
      "alpha",
      "Bravo",
      "charlie",
    ]);
    expect(rows.map((row) => row.id)).toEqual([
      main.id,
      `${main.id}:${unreachable.id}`,
      `${main.id}:${alpha.id}`,
      `${main.id}:${bravo.id}`,
      `${main.id}:${charlie.id}`,
    ]);
  });

  it.each([true, false, null])(
    "gives one empty row when sync_with_git is %s and there are no repositories",
    (syncWithGit) => {
      const branch = generateBranch({ id: "branch-x", sync_with_git: syncWithGit });

      const rows = toRows([branch], [[branch.id, generateBranchRepositoriesResult([])]]);

      expect(rows).toEqual([{ id: branch.id, branch, state: "empty", repository: null }]);
    }
  );

  it("lists read-only repositories on a branch not synced with Git", () => {
    const branch = generateBranch({ id: "branch-local", sync_with_git: false });
    const readOnly = generateBranchRepository({
      id: "repo-ro",
      name: "vendor-configs",
      kind: READONLY_REPOSITORY_KIND,
    });

    const rows = toRows([branch], [[branch.id, generateBranchRepositoriesResult([readOnly])]]);

    expect(rows).toEqual([{ id: branch.id, branch, state: "ok", repository: readOnly }]);
  });

  it("gives one anchor row for denied, error, pending and a missing entry", () => {
    expect(toRows([main], [[main.id, denied]])).toEqual([
      { id: main.id, branch: main, state: "denied", repository: null },
    ]);
    expect(toRows([main], [[main.id, failed]])).toEqual([
      {
        id: main.id,
        branch: main,
        state: "error",
        repository: null,
        errorMessage: "Server exploded",
      },
    ]);
    expect(toRows([main], [[main.id, pending]])).toEqual([
      { id: main.id, branch: main, state: "pending", repository: null },
    ]);
    expect(toRows([main], [])).toEqual([
      { id: main.id, branch: main, state: "pending", repository: null },
    ]);
  });

  it("keeps the anchor id across every state", () => {
    const fetches: BranchRepositoriesFetch[] = [
      pending,
      generateBranchRepositoriesResult([]),
      generateBranchRepositoriesResult([charlie, broken]),
      denied,
      failed,
    ];

    const anchorIds = fetches.map((fetch) => toRows([main], [[main.id, fetch]])[0]?.id);

    expect(anchorIds).toEqual(Array(fetches.length).fill(main.id));
  });

  it("keeps branch order with consecutive rows, isolating each branch's fetch", () => {
    // GIVEN two branches, the second listed first in the map
    const branches = [feature, main];
    const featureFetch = generateBranchRepositoriesResult([alpha, bravo]);
    const featureRows = toRows([feature], [[feature.id, featureFetch]]);

    // WHEN the other branch is denied, failed or loaded
    const results = [denied, failed, generateBranchRepositoriesResult([charlie])].map((fetch) =>
      toRows(branches, [
        [main.id, fetch],
        [feature.id, featureFetch],
      ])
    );

    // THEN the first branch's rows come first and are unchanged
    for (const rows of results) {
      expect(rows.slice(0, 2)).toEqual(featureRows);
      expect(rows.slice(2).every((row) => row.branch.id === main.id)).toBe(true);
    }
    expect(results[0]).toHaveLength(3);
    expect(results[2]?.[2]).toMatchObject({ id: main.id, state: "ok", repository: charlie });
  });
});
