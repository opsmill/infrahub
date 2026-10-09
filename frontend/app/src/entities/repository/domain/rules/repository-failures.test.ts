import { describe, expect, it } from "vitest";

import {
  generateBranchRepository,
  generateBranchRepositoryHealth,
  OPERATIONAL_STATUS,
  SYNC_STATUS,
} from "../../../../../tests/fake/branch-repositories";
import {
  countUnlistedFailures,
  getFailingRepositories,
  getFailureKind,
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
    expect(failing.map(getFailureKind)).toEqual(["import-error", "unreachable"]);
  });

  it("returns nothing before the health has loaded", () => {
    expect(getFailingRepositories(undefined)).toEqual([]);
  });
});

describe("countUnlistedFailures", () => {
  it("counts the failing repositories the server has past each list's limit", () => {
    // GIVEN
    const health = generateBranchRepositoryHealth({
      importErrors: [importError("a")],
      importErrorCount: 4,
      unreachable: [unreachable("b"), unreachable("c")],
      unreachableCount: 3,
    });

    // WHEN / THEN
    expect(countUnlistedFailures(health)).toBe(4);
  });

  it("is zero when every failing repository is listed, or before the health has loaded", () => {
    expect(
      countUnlistedFailures(generateBranchRepositoryHealth({ importErrors: [importError("a")] }))
    ).toBe(0);
    expect(countUnlistedFailures(undefined)).toBe(0);
  });

  it("doesn't count a listed repository again when the other list's limit left it out", () => {
    // GIVEN "both" has a band as an import error and is also past the unreachable list's limit
    const both = generateBranchRepository({
      id: "both",
      name: "both",
      syncStatus: SYNC_STATUS.importError,
      operationalStatus: OPERATIONAL_STATUS.errorCred,
    });
    const health = generateBranchRepositoryHealth({
      importErrors: [both],
      importErrorCount: 1,
      unreachable: [unreachable("b")],
      unreachableCount: 3,
    });

    // WHEN / THEN only the one other unreachable repository is unlisted
    expect(countUnlistedFailures(health)).toBe(1);
  });

  it("counts a repository listed in both lists once", () => {
    // GIVEN
    const both = generateBranchRepository({
      id: "both",
      name: "both",
      syncStatus: SYNC_STATUS.importError,
      operationalStatus: OPERATIONAL_STATUS.errorCred,
    });
    const health = generateBranchRepositoryHealth({
      importErrors: [both],
      importErrorCount: 1,
      unreachable: [both],
      unreachableCount: 1,
    });

    // WHEN / THEN
    expect(countUnlistedFailures(health)).toBe(0);
  });
});

describe("getFailureKind", () => {
  it("returns import-error or unreachable", () => {
    expect(getFailureKind(importError("a"))).toBe("import-error");
    expect(getFailureKind(unreachable("a"))).toBe("unreachable");
  });
});
