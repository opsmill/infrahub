import { describe, expect, it } from "vitest";

import { getRepositoryImportErrorQueryOptions } from "@/entities/repository/ui/queries/get-repository-import-error.query";

const params = { branchName: "feature", repositoryId: "repo-1" };

describe("getRepositoryImportErrorQueryOptions", () => {
  it("polls every 10 seconds while a repository is syncing", () => {
    expect(
      getRepositoryImportErrorQueryOptions({ ...params, isSyncing: true }).refetchInterval
    ).toBe(10_000);
  });

  it("doesn't poll when no repository is syncing", () => {
    expect(
      getRepositoryImportErrorQueryOptions({ ...params, isSyncing: false }).refetchInterval
    ).toBe(false);
  });
});
