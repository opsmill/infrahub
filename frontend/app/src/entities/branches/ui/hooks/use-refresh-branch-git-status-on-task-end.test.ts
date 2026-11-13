import { QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { queryClient } from "@/shared/api/rest/client";

import { branchGitStatusQueryKeys } from "@/entities/branch-git-status/ui/queries/branch-git-status.query-keys";
import { useRefreshBranchGitStatusOnTaskEnd } from "@/entities/branches/ui/hooks/use-refresh-branch-git-status-on-task-end";
import { isTaskFinished } from "@/entities/tasks/domain/use-cases/is-task-finished";

vi.mock("@/entities/tasks/domain/use-cases/is-task-finished");

const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(QueryClientProvider, { client: queryClient }, children);

const gitStatusInvalidations = () =>
  vi
    .mocked(queryClient.invalidateQueries)
    .mock.calls.filter(([filters]) => filters?.queryKey === branchGitStatusQueryKeys.all).length;

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.resetAllMocks();
  queryClient.clear();
});

describe("useRefreshBranchGitStatusOnTaskEnd", () => {
  test("checks nothing until a task is known", async () => {
    // WHEN
    await renderHook(() => useRefreshBranchGitStatusOnTaskEnd(null), { wrapper });

    // THEN
    expect(isTaskFinished).not.toHaveBeenCalled();
  });

  test("refreshes the branch Git status once when the task ends, then stops checking", async () => {
    // GIVEN a task that ends on the second check
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(isTaskFinished).mockResolvedValueOnce(false).mockResolvedValue(true);
    vi.spyOn(queryClient, "invalidateQueries");

    // WHEN the task is still running
    await renderHook(() => useRefreshBranchGitStatusOnTaskEnd("task-1"), { wrapper });
    await expect.poll(() => vi.mocked(isTaskFinished).mock.calls.length).toBe(1);

    // THEN the Git status is left alone
    expect(gitStatusInvalidations()).toBe(0);

    // WHEN the next check finds the task ended
    await vi.advanceTimersByTimeAsync(5000);

    // THEN the Git status is refreshed once
    await expect.poll(() => gitStatusInvalidations()).toBe(1);
    expect(isTaskFinished).toHaveBeenCalledWith({ taskId: "task-1" });

    // WHEN more time passes
    await vi.advanceTimersByTimeAsync(15_000);

    // THEN the task is not checked again and the Git status is not refreshed again
    expect(isTaskFinished).toHaveBeenCalledTimes(2);
    expect(gitStatusInvalidations()).toBe(1);
  });
});
