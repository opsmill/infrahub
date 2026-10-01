import { QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { queryClient } from "@/shared/api/rest/client";

import { createBranch } from "@/entities/branches/domain/use-cases/create-branch";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { useCreateBranchMutation } from "@/entities/branches/ui/queries/create-branch.mutation";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

import { generateBranch } from "../../../../../tests/fake/branch";

vi.mock("@/entities/branches/domain/use-cases/create-branch");

const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(QueryClientProvider, { client: queryClient }, children);

const branchInput = { name: "feature-1" } as Parameters<typeof createBranch>[0];

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useCreateBranchMutation", () => {
  test("refetches branches and invalidates repositories once a branch is created", async () => {
    // GIVEN
    vi.mocked(createBranch).mockResolvedValue(generateBranch({ name: "feature-1" }));
    const refetchSpy = vi.spyOn(queryClient, "refetchQueries");
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = await renderHook(() => useCreateBranchMutation(), { wrapper });

    // WHEN
    await result.current.mutateAsync(branchInput);

    // THEN
    await expect
      .poll(() => invalidateSpy)
      .toHaveBeenCalledWith({ queryKey: repositoryQueryKeys.all });
    expect(refetchSpy).toHaveBeenCalledWith({ queryKey: branchesQueryKeys.all });
  });

  test("touches no cache when the use case creates nothing", async () => {
    // GIVEN
    vi.mocked(createBranch).mockResolvedValue(
      undefined as unknown as Awaited<ReturnType<typeof createBranch>>
    );
    const refetchSpy = vi.spyOn(queryClient, "refetchQueries");
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = await renderHook(() => useCreateBranchMutation(), { wrapper });

    // WHEN
    await result.current.mutateAsync(branchInput);

    // THEN
    expect(refetchSpy).not.toHaveBeenCalledWith({ queryKey: branchesQueryKeys.all });
    expect(invalidateSpy).not.toHaveBeenCalledWith({ queryKey: repositoryQueryKeys.all });
  });
});
