import { describe, expect, it } from "vitest";

import {
  generateBranchRepository,
  OPERATIONAL_STATUS,
  SYNC_STATUS,
} from "../../../../../tests/fake/branch-repositories";
import {
  getBandKind,
  getFailingRepositories,
  getRepositoryRank,
  hasImportError,
  isRepositoryUnreachable,
  rankRepositories,
} from "./rank-repositories";

const importError = (name: string) =>
  generateBranchRepository({ id: name, name, syncStatus: SYNC_STATUS.importError });
const unreachable = (name: string) =>
  generateBranchRepository({ id: name, name, operationalStatus: OPERATIONAL_STATUS.errorCred });
const healthy = (name: string) => generateBranchRepository({ id: name, name });

describe("hasImportError", () => {
  it("is true only for the error-import sync status", () => {
    expect(hasImportError(importError("a"))).toBe(true);
    expect(hasImportError(healthy("a"))).toBe(false);
    expect(hasImportError(generateBranchRepository({ syncStatus: SYNC_STATUS.syncing }))).toBe(
      false
    );
  });
});

describe("isRepositoryUnreachable", () => {
  it.each(["error-cred", "error-connection", "error"])("is true for %s", (value) => {
    const repository = generateBranchRepository({ operationalStatus: { value, label: value } });
    expect(isRepositoryUnreachable(repository)).toBe(true);
  });

  it.each(["online", "unknown", null])("is false for %s", (value) => {
    const repository = generateBranchRepository({ operationalStatus: { value, label: null } });
    expect(isRepositoryUnreachable(repository)).toBe(false);
  });
});

describe("getRepositoryRank", () => {
  it("ranks import errors above unreachable above the rest", () => {
    expect(getRepositoryRank(importError("a"))).toBe(2);
    expect(getRepositoryRank(unreachable("a"))).toBe(1);
    expect(getRepositoryRank(healthy("a"))).toBe(0);
  });

  it("ranks a repository that is both failing as an import error", () => {
    const both = generateBranchRepository({
      syncStatus: SYNC_STATUS.importError,
      operationalStatus: OPERATIONAL_STATUS.errorConnection,
    });
    expect(getRepositoryRank(both)).toBe(2);
  });
});

describe("rankRepositories", () => {
  it("puts import errors first, then unreachable, then the rest, by name inside each group", () => {
    const repositories = [
      healthy("delta"),
      unreachable("zulu"),
      importError("yankee"),
      healthy("Alpha"),
      unreachable("bravo"),
      importError("charlie"),
    ];

    expect(rankRepositories(repositories).map((r) => r.name)).toEqual([
      "charlie",
      "yankee",
      "bravo",
      "zulu",
      "Alpha",
      "delta",
    ]);
  });

  it("keeps the input order for repositories with the same rank and name", () => {
    const first = generateBranchRepository({ id: "first", name: "same" });
    const second = generateBranchRepository({ id: "second", name: "same" });

    expect(rankRepositories([first, second]).map((r) => r.id)).toEqual(["first", "second"]);
    expect(rankRepositories([second, first]).map((r) => r.id)).toEqual(["second", "first"]);
  });

  it("does not mutate its input", () => {
    const repositories = [healthy("b"), importError("a")];
    const snapshot = [...repositories];

    const ranked = rankRepositories(repositories);

    expect(repositories).toEqual(snapshot);
    expect(ranked).not.toBe(repositories);
  });
});

describe("getFailingRepositories", () => {
  it("returns only failing repositories, ranked", () => {
    const repositories = [healthy("a"), unreachable("b"), importError("c"), healthy("d")];

    expect(getFailingRepositories(repositories).map((r) => r.name)).toEqual(["c", "b"]);
  });

  it("returns an empty list when nothing fails", () => {
    expect(getFailingRepositories([healthy("a")])).toEqual([]);
  });
});

describe("getBandKind", () => {
  it("returns import-error or unreachable", () => {
    expect(getBandKind(importError("a"))).toBe("import-error");
    expect(getBandKind(unreachable("a"))).toBe("unreachable");
  });

  it("prefers import-error when both apply", () => {
    const both = generateBranchRepository({
      syncStatus: SYNC_STATUS.importError,
      operationalStatus: OPERATIONAL_STATUS.error,
    });
    expect(getBandKind(both)).toBe("import-error");
  });
});
