import { describe, expect, it } from "vitest";

import {
  generateBranchRepository,
  generateBranchRepositoryHealth,
  OPERATIONAL_STATUS,
  SYNC_STATUS,
} from "../../../../../tests/fake/branch-repositories";
import { isAnyRepositorySyncing } from "./is-any-repository-syncing";
import {
  getBandKind,
  getFailingRepositories,
  hasImportError,
  isRepositoryUnreachable,
} from "./repository-failures";

const importError = (name: string) =>
  generateBranchRepository({ id: name, name, syncStatus: SYNC_STATUS.importError });
const unreachable = (name: string) =>
  generateBranchRepository({ id: name, name, operationalStatus: OPERATIONAL_STATUS.errorCred });

describe("hasImportError", () => {
  it("is true only for the error-import sync status", () => {
    expect(hasImportError(importError("a"))).toBe(true);
    expect(hasImportError(generateBranchRepository())).toBe(false);
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

describe("getFailingRepositories", () => {
  it("lists import errors first, then unreachable repositories, in the server's order", () => {
    // GIVEN
    const health = generateBranchRepositoryHealth({
      importErrors: [importError("charlie"), importError("yankee")],
      unreachable: [unreachable("bravo"), unreachable("zulu")],
    });

    // WHEN
    const names = getFailingRepositories(health).map(({ name }) => name);

    // THEN
    expect(names).toEqual(["charlie", "yankee", "bravo", "zulu"]);
  });

  it("lists a repository that is both failing and unreachable once, as an import error", () => {
    // GIVEN
    const both = generateBranchRepository({
      id: "both",
      syncStatus: SYNC_STATUS.importError,
      operationalStatus: OPERATIONAL_STATUS.error,
    });
    const health = generateBranchRepositoryHealth({
      importErrors: [both],
      unreachable: [both, unreachable("other")],
    });

    // WHEN
    const failing = getFailingRepositories(health);

    // THEN
    expect(failing.map(({ id }) => id)).toEqual(["both", "other"]);
    expect(failing.map(getBandKind)).toEqual(["import-error", "unreachable"]);
  });

  it("returns nothing before the health has loaded", () => {
    expect(getFailingRepositories(undefined)).toEqual([]);
  });
});

describe("getBandKind", () => {
  it("returns import-error or unreachable", () => {
    expect(getBandKind(importError("a"))).toBe("import-error");
    expect(getBandKind(unreachable("a"))).toBe("unreachable");
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
