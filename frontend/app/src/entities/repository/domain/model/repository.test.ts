import { describe, expect, it } from "vitest";

import {
  IMPORT_LOG_LIMIT,
  IMPORT_WORKFLOWS,
  MAX_VISIBLE_BANDS,
  REPOSITORY_FETCH_LIMIT,
  REPOSITORY_OPERATIONAL_ERRORS,
  REPOSITORY_SYNC_STATUS_IMPORT_ERROR,
  REPOSITORY_SYNC_STATUS_SYNCING,
} from "./repository";

// Values mirror backend enums and flow names; a rename there must fail here.
describe("repository constants", () => {
  it("matches the backend sync and operational status values", () => {
    expect(REPOSITORY_SYNC_STATUS_IMPORT_ERROR).toBe("error-import");
    expect(REPOSITORY_SYNC_STATUS_SYNCING).toBe("syncing");
    expect(REPOSITORY_OPERATIONAL_ERRORS).toEqual(["error-cred", "error-connection", "error"]);
  });

  it("lists every flow that imports a repository into a branch", () => {
    expect(IMPORT_WORKFLOWS).toEqual([
      "git-repository-add-read-write",
      "git-repository-add-read-only",
      "git-repository-import-object",
      "git-read-only-repository-import-last-commit",
      "git-repository-pull-read-only",
      "sync-git-repo-with-origin",
    ]);
  });

  it("uses the fetch limits and band count from the design", () => {
    expect(REPOSITORY_FETCH_LIMIT).toBe(500);
    expect(IMPORT_LOG_LIMIT).toBe(10_000);
    expect(MAX_VISIBLE_BANDS).toBe(3);
  });
});
