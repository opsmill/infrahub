import { QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { queryClient } from "@/shared/api/rest/client";

import { branchGitStatusQueryKeys } from "@/entities/branch-git-status/ui/queries/branch-git-status.query-keys";
import { rebaseBranch } from "@/entities/branches/domain/use-cases/rebase-branch";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { useRebaseBranch } from "@/entities/branches/ui/queries/rebase-branch.mutation";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

vi.mock("@/entities/branches/domain/use-cases/rebase-branch");

const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(QueryClientProvider, { client: queryClient }, children);

afterEach(() => {
  vi.restoreAllMocks();
  queryClient.clear();
});

describe("useRebaseBranch", () => {
  test("invalidates branches, tasks and branch Git status once the rebase succeeds", async () => {
    // GIVEN
    vi.mocked(rebaseBranch).mockResolvedValue({} as Awaited<ReturnType<typeof rebaseBranch>>);
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = await renderHook(() => useRebaseBranch(), { wrapper });

    // WHEN
    await result.current.mutateAsync({ branchName: "feature-1" });

    // THEN
    await expect
      .poll(() => invalidateSpy)
      .toHaveBeenCalledWith({ queryKey: branchGitStatusQueryKeys.all });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: branchesQueryKeys.all });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: tasksQueryKeys.all });
  });
});
