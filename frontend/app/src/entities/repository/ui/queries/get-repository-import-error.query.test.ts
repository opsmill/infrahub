import { describe, expect, it } from "vitest";

import {
  getImportTaskErrorMessageQueryOptions,
  getRepositoryImportTaskQueryOptions,
} from "@/entities/repository/ui/queries/get-repository-import-error.query";

const params = { branchName: "feature", repositoryId: "repo-1" };

describe("getRepositoryImportTaskQueryOptions", () => {
  it("polls for the failed task every 10 seconds while a repository is syncing", () => {
    expect(
      getRepositoryImportTaskQueryOptions({ ...params, isSyncing: true }).refetchInterval
    ).toBe(10_000);
  });

  it("doesn't poll when no repository is syncing", () => {
    expect(
      getRepositoryImportTaskQueryOptions({ ...params, isSyncing: false }).refetchInterval
    ).toBe(false);
  });
});

describe("getImportTaskErrorMessageQueryOptions", () => {
  it("fetches a task's log once, keyed on the task, and never polls it", () => {
    const options = getImportTaskErrorMessageQueryOptions("task-1");

    expect(options.queryKey).toEqual(["repository", "import-log", "task-1"]);
    expect(options.enabled).toBe(true);
    expect(options.staleTime).toBe(Number.POSITIVE_INFINITY);
    expect(options.refetchInterval).toBeUndefined();
  });

  it("asks for a new log only when the failed task changes", () => {
    expect(getImportTaskErrorMessageQueryOptions("task-1").queryKey).not.toEqual(
      getImportTaskErrorMessageQueryOptions("task-2").queryKey
    );
  });

  it("doesn't fetch a log until a failed task is known", () => {
    expect(getImportTaskErrorMessageQueryOptions(undefined).enabled).toBe(false);
    expect(getImportTaskErrorMessageQueryOptions(null).enabled).toBe(false);
  });
});
