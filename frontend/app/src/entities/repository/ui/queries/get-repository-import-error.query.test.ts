import { type Query, QueryClient, QueryClientProvider, skipToken } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { getImportTaskErrorMessage } from "@/entities/repository/domain/use-cases/get-import-task-error-message";
import { getLatestRepositoryImportTask } from "@/entities/repository/domain/use-cases/get-latest-repository-import-task";
import {
  getImportTaskErrorMessageQueryOptions,
  getLatestRepositoryImportTaskQueryOptions,
  useGetRepositoryImportError,
} from "@/entities/repository/ui/queries/get-repository-import-error.query";

vi.mock("@/entities/repository/domain/use-cases/get-import-task-error-message");
vi.mock("@/entities/repository/domain/use-cases/get-latest-repository-import-task");

// The transport throws an Error whose cause is an error carrying the GraphQL errors.
const permissionDenied = () =>
  new Error("Denied", {
    cause: Object.assign(new Error("Denied"), {
      graphQLErrors: [
        {
          message: "Denied",
          extensions: { code: "PERMISSION_DENIED", http_status: 403, data: {} },
        },
      ],
    }),
  });

const params = { branchName: "feature", repositoryId: "repo-1" };

const taskRefetchIntervalFor = (isSyncing: boolean, state: Partial<Query["state"]>) => {
  const { refetchInterval } = getLatestRepositoryImportTaskQueryOptions({ ...params, isSyncing });
  if (typeof refetchInterval !== "function") throw new Error("expected a refetch function");
  return refetchInterval({ state } as never);
};

const renderImportError = async () => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
  const { result } = await renderHook(
    () => useGetRepositoryImportError({ ...params, isSyncing: false }),
    { wrapper }
  );
  return { queryClient, result };
};

describe("getLatestRepositoryImportTaskQueryOptions", () => {
  it("polls every 10 seconds while a repository is syncing", () => {
    expect(taskRefetchIntervalFor(true, { data: { status: "none" } })).toBe(10_000);
  });

  it("polls while the newest import is still running", () => {
    expect(taskRefetchIntervalFor(false, { data: { status: "running" } })).toBe(10_000);
  });

  it("fetches once otherwise", () => {
    expect(taskRefetchIntervalFor(false, { data: { status: "failed", taskId: "task-1" } })).toBe(
      false
    );
    expect(taskRefetchIntervalFor(false, { data: { status: "none" } })).toBe(false);
  });

  it("retries a failed lookup every minute, and stops once it is denied", () => {
    expect(
      taskRefetchIntervalFor(false, {
        status: "error",
        data: undefined,
        error: new Error("Network"),
      })
    ).toBe(60_000);
    expect(
      taskRefetchIntervalFor(true, { status: "error", data: undefined, error: permissionDenied() })
    ).toBe(false);
  });
});

describe("getImportTaskErrorMessageQueryOptions", () => {
  it("fetches a task's log once, keyed on the task", () => {
    const options = getImportTaskErrorMessageQueryOptions({ taskId: "task-1" });

    expect(options.queryKey).toEqual(["repository", "import-log", { taskId: "task-1" }]);
    expect(options.staleTime).toBe(Number.POSITIVE_INFINITY);
    expect(options.refetchInterval).toBeUndefined();
  });

  it("doesn't fetch a log until a failed task is known", () => {
    expect(getImportTaskErrorMessageQueryOptions({ taskId: undefined }).queryFn).toBe(skipToken);
  });
});

describe("useGetRepositoryImportError", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows the failed run's last error line", async () => {
    // GIVEN
    vi.mocked(getLatestRepositoryImportTask).mockResolvedValue({
      status: "failed",
      taskId: "task-1",
    });
    vi.mocked(getImportTaskErrorMessage).mockResolvedValue("Unable to load the schema");

    // WHEN
    const { result } = await renderImportError();

    // THEN
    await expect
      .poll(() => result.current)
      .toEqual({ status: "found", taskId: "task-1", message: "Unable to load the schema" });
    expect(getImportTaskErrorMessage).toHaveBeenCalledWith({ taskId: "task-1", logLimit: 10_000 });
  });

  it("reads a failed log fetch as details not found, then shows the error once a refetch succeeds", async () => {
    // GIVEN
    vi.mocked(getLatestRepositoryImportTask).mockResolvedValue({
      status: "failed",
      taskId: "task-1",
    });
    vi.mocked(getImportTaskErrorMessage)
      .mockRejectedValueOnce(new Error("Log fetch failed"))
      .mockResolvedValue("Unable to load the schema");
    const { queryClient, result } = await renderImportError();
    await expect.poll(() => result.current).toEqual({ status: "not-found", taskId: "task-1" });

    // WHEN
    await queryClient.refetchQueries({
      queryKey: ["repository", "import-log", { taskId: "task-1" }],
    });

    // THEN
    await expect
      .poll(() => result.current)
      .toEqual({ status: "found", taskId: "task-1", message: "Unable to load the schema" });
  });

  it("keeps the details loading while the newest import is running", async () => {
    // GIVEN
    vi.mocked(getLatestRepositoryImportTask).mockResolvedValue({ status: "running" });

    // WHEN
    const { queryClient, result } = await renderImportError();

    // THEN
    await expect
      .poll(() => queryClient.getQueryData(["repository", "latest-import-task", params]))
      .toEqual({ status: "running" });
    expect(result.current).toBeUndefined();
    expect(getImportTaskErrorMessage).not.toHaveBeenCalled();
  });

  it("reads no matching import as details not found", async () => {
    // GIVEN
    vi.mocked(getLatestRepositoryImportTask).mockResolvedValue({ status: "none" });

    // WHEN
    const { result } = await renderImportError();

    // THEN
    await expect.poll(() => result.current).toEqual({ status: "not-found", taskId: null });
  });

  it("reads a failed lookup as details not found, without asking again", async () => {
    // GIVEN
    vi.mocked(getLatestRepositoryImportTask).mockRejectedValue(new Error("Lookup failed"));

    // WHEN
    const { result } = await renderImportError();

    // THEN
    await expect.poll(() => result.current).toEqual({ status: "not-found", taskId: null });
    expect(getLatestRepositoryImportTask).toHaveBeenCalledTimes(1);
  });
});
