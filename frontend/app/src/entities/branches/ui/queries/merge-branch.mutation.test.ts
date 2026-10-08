import { QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { queryClient } from "@/shared/api/rest/client";

import { branchGitStatusQueryKeys } from "@/entities/branch-git-status/ui/queries/branch-git-status.query-keys";
import { mergeBranch } from "@/entities/branches/domain/use-cases/merge-branch";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { useMergeBranch } from "@/entities/branches/ui/queries/merge-branch.mutation";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

vi.mock("@/entities/branches/domain/use-cases/merge-branch");

const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(QueryClientProvider, { client: queryClient }, children);

afterEach(() => {
  vi.restoreAllMocks();
  queryClient.clear();
});

describe("useMergeBranch", () => {
  test("invalidates branches, tasks and branch Git status once the merge succeeds", async () => {
    // GIVEN
    vi.mocked(mergeBranch).mockResolvedValue({} as Awaited<ReturnType<typeof mergeBranch>>);
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = await renderHook(() => useMergeBranch(), { wrapper });

    // WHEN
    await result.current.mutateAsync({ branchName: "feature-1" } as Parameters<
      typeof mergeBranch
    >[0]);

    // THEN
    await expect
      .poll(() => invalidateSpy)
      .toHaveBeenCalledWith({ queryKey: branchGitStatusQueryKeys.all });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: branchesQueryKeys.all });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: tasksQueryKeys.all });
  });
});
