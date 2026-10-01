import { QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { queryClient } from "@/shared/api/rest/client";

import { mergeBranch } from "@/entities/branches/domain/use-cases/merge-branch";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { useMergeBranch } from "@/entities/branches/ui/queries/merge-branch.mutation";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

vi.mock("@/entities/branches/domain/use-cases/merge-branch");

const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(QueryClientProvider, { client: queryClient }, children);

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useMergeBranch", () => {
  test("invalidates branches and repository status once the branch operation succeeds", async () => {
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
      .toHaveBeenCalledWith({ queryKey: repositoryQueryKeys.all });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: branchesQueryKeys.all });
  });
});
