import { QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { queryClient } from "@/shared/api/rest/client";

import { deleteBranches } from "@/entities/branches/domain/use-cases/delete-branches";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { useDeleteBranchesMutation } from "@/entities/branches/ui/queries/delete-branches.mutation";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

vi.mock("@/entities/branches/domain/use-cases/delete-branches");

const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(QueryClientProvider, { client: queryClient }, children);

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useDeleteBranchesMutation", () => {
  test("invalidates branches and repository status once the deletion succeeds", async () => {
    // GIVEN
    vi.mocked(deleteBranches).mockResolvedValue({ deleted: ["feature-1"], failed: [] } as Awaited<
      ReturnType<typeof deleteBranches>
    >);
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = await renderHook(() => useDeleteBranchesMutation(), { wrapper });

    // WHEN
    await result.current.mutateAsync({ names: ["feature-1"], deleteFromGit: false } as Parameters<
      typeof deleteBranches
    >[0]);

    // THEN
    await expect
      .poll(() => invalidateSpy)
      .toHaveBeenCalledWith({ queryKey: repositoryQueryKeys.all });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: branchesQueryKeys.all });
  });
});
