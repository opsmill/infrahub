import { QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { queryClient } from "@/shared/api/rest/client";

import { branchGitStatusQueryKeys } from "@/entities/branch-git-status/ui/queries/branch-git-status.query-keys";
import { deleteBranch } from "@/entities/branches/domain/use-cases/delete-branch";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { useDeleteBranchMutation } from "@/entities/branches/ui/queries/delete-branch.mutation";

vi.mock("@/entities/branches/domain/use-cases/delete-branch");

const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(QueryClientProvider, { client: queryClient }, children);

afterEach(() => {
  vi.restoreAllMocks();
  queryClient.clear();
});

describe("useDeleteBranchMutation", () => {
  test("invalidates branches and branch Git status once the deletion succeeds", async () => {
    // GIVEN
    vi.mocked(deleteBranch).mockResolvedValue("feature-1");
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = await renderHook(() => useDeleteBranchMutation(), { wrapper });

    // WHEN
    await result.current.mutateAsync({ name: "feature-1" });

    // THEN
    await expect
      .poll(() => invalidateSpy)
      .toHaveBeenCalledWith({ queryKey: branchGitStatusQueryKeys.all });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: branchesQueryKeys.all });
  });
});
