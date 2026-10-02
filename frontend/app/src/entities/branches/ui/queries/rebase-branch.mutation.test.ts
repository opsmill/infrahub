import { QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { queryClient } from "@/shared/api/rest/client";

import { rebaseBranch } from "@/entities/branches/domain/use-cases/rebase-branch";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { useRebaseBranch } from "@/entities/branches/ui/queries/rebase-branch.mutation";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

vi.mock("@/entities/branches/domain/use-cases/rebase-branch");

const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(QueryClientProvider, { client: queryClient }, children);

afterEach(() => {
  vi.restoreAllMocks();
  queryClient.clear();
});

describe("useRebaseBranch", () => {
  test("invalidates branches, tasks and repository status once the branch operation succeeds", async () => {
    // GIVEN
    vi.mocked(rebaseBranch).mockResolvedValue({} as Awaited<ReturnType<typeof rebaseBranch>>);
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = await renderHook(() => useRebaseBranch(), { wrapper });

    // WHEN
    await result.current.mutateAsync({ branchName: "feature-1" } as Parameters<
      typeof rebaseBranch
    >[0]);

    // THEN
    await expect
      .poll(() => invalidateSpy)
      .toHaveBeenCalledWith({ queryKey: repositoryQueryKeys.all });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: branchesQueryKeys.all });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: tasksQueryKeys.all });
  });
});
