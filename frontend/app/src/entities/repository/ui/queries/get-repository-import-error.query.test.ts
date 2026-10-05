import { type Query, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CombinedError } from "@urql/core";
import { GraphQLError } from "graphql";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { ERROR_CODES } from "@/shared/api/errors";

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

const taskQueryIn = (state: Partial<Query["state"]>) =>
  ({ state: { status: "success", dataUpdateCount: 1, ...state } }) as never;

const taskRefetchIntervalFor = (isSyncing: boolean, state: Partial<Query["state"]>) => {
  const { refetchInterval } = getRepositoryImportTaskQueryOptions({ ...params, isSyncing });
  if (typeof refetchInterval !== "function") throw new Error("expected a refetch function");
  return refetchInterval(taskQueryIn(state));
};

const permissionDenied = () =>
  new Error("Denied", {
    cause: new CombinedError({
      graphQLErrors: [
        new GraphQLError("Denied", { extensions: { code: ERROR_CODES.PERMISSION_DENIED } }),
      ],
    }),
  });

const failed = { lookup: { status: "failed", taskId: "task-1" }, notFoundCount: 0 };
const running = { lookup: { status: "running" }, notFoundCount: 0 };
const notFound = (notFoundCount: number) => ({ lookup: { status: "not-found" }, notFoundCount });

describe("getRepositoryImportTaskQueryOptions", () => {
  it("polls for the failed task every 10 seconds while a repository is syncing", () => {
    expect(taskRefetchIntervalFor(true, { data: failed })).toBe(10_000);
  });

  it("looks for the failed task again while none is found, a limited number of times", () => {
    expect(taskRefetchIntervalFor(false, { data: notFound(1) })).toBe(10_000);
    expect(taskRefetchIntervalFor(false, { data: notFound(6) })).toBe(false);
  });

  it("keeps polling for as long as an import runs, whatever the number of lookups", () => {
    expect(taskRefetchIntervalFor(false, { data: running, dataUpdateCount: 20 })).toBe(10_000);
  });

  it("stops looking once the failed task is found", () => {
    expect(taskRefetchIntervalFor(false, { data: failed })).toBe(false);
  });

  it("stops on a denied lookup and slows down after any other failure", () => {
    expect(
      taskRefetchIntervalFor(true, { status: "error", data: undefined, error: permissionDenied() })
    ).toBe(false);
    expect(taskRefetchIntervalFor(false, { status: "error", data: undefined })).toBe(60_000);
    expect(taskRefetchIntervalFor(false, { status: "error", data: notFound(6) })).toBe(60_000);
  });

  it("counts only the lookups that find nothing, starting again after a running import", async () => {
    // GIVEN
    const queryClient = new QueryClient();
    const options = getRepositoryImportTaskQueryOptions({ ...params, isSyncing: false });
    vi.mocked(getRepositoryImportTask)
      .mockResolvedValueOnce({ status: "not-found" })
      .mockResolvedValueOnce({ status: "not-found" })
      .mockResolvedValueOnce({ status: "running" })
      .mockResolvedValueOnce({ status: "not-found" });

    // WHEN
    const counts: number[] = [];
    for (let lookup = 0; lookup < 4; lookup++) {
      const result = await queryClient.fetchQuery({ ...options, staleTime: 0 });
      counts.push(result.notFoundCount);
    }

    // THEN
    expect(counts).toEqual([1, 2, 0, 1]);
  });
});

describe("getImportTaskErrorMessageQueryOptions", () => {
  it("fetches a task's log once, keyed on the task", () => {
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

describe("useGetRepositoryImportError", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("reads a failed log fetch as details not found, then shows the error once a refetch succeeds", async () => {
    // GIVEN
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children);
    vi.mocked(getRepositoryImportTask).mockResolvedValue({ status: "failed", taskId: "task-1" });
    vi.mocked(getImportTaskErrorMessage)
      .mockRejectedValueOnce(permissionDenied())
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

describe("useGetRepositoryImportError while an import is running", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("keeps the details loading instead of reading them as not found", async () => {
    // GIVEN
    const queryClient = new QueryClient();
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children);
    vi.mocked(getRepositoryImportTask).mockResolvedValue({ status: "running" });

    // WHEN
    const { result } = await renderHook(
      () => useGetRepositoryImportError({ ...params, isSyncing: false }),
      { wrapper }
    );

    // THEN
    await expect.poll(() => getRepositoryImportTask).toHaveBeenCalled();
    await expect
      .poll(() => queryClient.getQueryData(["repository", "import-task", params]))
      .toEqual(running);
    expect(result.current).toBeUndefined();
  });
});

describe("useGetRepositoryImportError when the task lookup fails", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("reads it as details not found, without asking again after a denial", async () => {
    // GIVEN
    const queryClient = new QueryClient();
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children);
    vi.mocked(getRepositoryImportTask).mockRejectedValue(permissionDenied());

    // WHEN
    const { result } = await renderHook(
      () => useGetRepositoryImportError({ ...params, isSyncing: false }),
      { wrapper }
    );

    // THEN
    await expect.poll(() => result.current).toEqual({ status: "not-found", taskId: null });
    expect(getRepositoryImportTask).toHaveBeenCalledTimes(1);
  });
});
