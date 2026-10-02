import { type Query, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import {
  getImportTaskErrorMessage,
  getRepositoryImportTask,
} from "@/entities/repository/domain/use-cases/get-repository-import-error";
import {
  getImportTaskErrorMessageQueryOptions,
  getRepositoryImportTaskQueryOptions,
  useGetRepositoryImportError,
} from "@/entities/repository/ui/queries/get-repository-import-error.query";

vi.mock("@/entities/repository/domain/use-cases/get-repository-import-error");

const params = { branchName: "feature", repositoryId: "repo-1" };

const logQueryIn = (status: "error" | "success") =>
  ({ state: { status, data: status === "success" ? null : undefined } }) as unknown as Query<
    string | null,
    Error,
    string | null,
    readonly ["repository", "import-log", string]
  >;

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
  it("fetches a task's log once, keyed on the task", () => {
    const options = getImportTaskErrorMessageQueryOptions("task-1");

    expect(options.queryKey).toEqual(["repository", "import-log", "task-1"]);
    expect(options.enabled).toBe(true);
    expect(options.staleTime).toBe(Number.POSITIVE_INFINITY);
  });

  it("polls a log only while its fetch is failing", () => {
    const { refetchInterval } = getImportTaskErrorMessageQueryOptions("task-1");
    if (typeof refetchInterval !== "function") throw new Error("expected a refetch function");

    expect(refetchInterval(logQueryIn("error"))).toBe(10_000);
    expect(refetchInterval(logQueryIn("success"))).toBe(false);
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

describe("useGetRepositoryImportError", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("reads a failed log fetch as details not found, then shows the error once a retry succeeds", async () => {
    // GIVEN
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children);
    vi.mocked(getRepositoryImportTask).mockResolvedValue("task-1");
    vi.mocked(getImportTaskErrorMessage)
      .mockRejectedValueOnce(new Error("Network error"))
      .mockResolvedValue("Unable to load the schema");
    const { result } = await renderHook(
      () => useGetRepositoryImportError({ ...params, isSyncing: false }),
      { wrapper }
    );
    await expect.poll(() => result.current).toEqual({ status: "not-found", taskId: "task-1" });

    // WHEN
    await queryClient.refetchQueries({ queryKey: ["repository", "import-log", "task-1"] });

    // THEN
    await expect
      .poll(() => result.current)
      .toEqual({ status: "found", taskId: "task-1", message: "Unable to load the schema" });
  });
});
