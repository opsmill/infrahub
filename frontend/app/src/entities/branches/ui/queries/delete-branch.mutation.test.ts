import { QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { queryClient } from "@/shared/api/rest/client";

import { deleteBranch } from "@/entities/branches/domain/use-cases/delete-branch";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { useDeleteBranchMutation } from "@/entities/branches/ui/queries/delete-branch.mutation";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

vi.mock("@/entities/branches/domain/use-cases/delete-branch");

const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(QueryClientProvider, { client: queryClient }, children);

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useDeleteBranchMutation", () => {
  test("invalidates branches and repository status once the deletion succeeds", async () => {
    // GIVEN
    vi.mocked(deleteBranch).mockResolvedValue(
      "feature-1" as Awaited<ReturnType<typeof deleteBranch>>
    );
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = await renderHook(() => useDeleteBranchMutation(), { wrapper });

    // WHEN
    await result.current.mutateAsync({ name: "feature-1" });

    // THEN
    await expect
      .poll(() => invalidateSpy)
      .toHaveBeenCalledWith({ queryKey: repositoryQueryKeys.all });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: branchesQueryKeys.all });
  });
});
