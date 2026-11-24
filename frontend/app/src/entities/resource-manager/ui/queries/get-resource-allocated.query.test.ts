import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { graphqlClient } from "@/shared/api/graphql/client";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useGetResourceAllocated } from "@/entities/resource-manager/ui/queries/get-resource-allocated.query";

import { generateBranch } from "../../../../../tests/fake/branch";

vi.mock("@/entities/branches/ui/branches-provider");

describe("useGetResourceAllocated", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("requests the allocated resources on the current branch", async () => {
    // GIVEN
    vi.mocked(useCurrentBranch).mockReturnValue({
      currentBranch: generateBranch({ name: "feat-pool" }),
    } as ReturnType<typeof useCurrentBranch>);
    const querySpy = vi.spyOn(graphqlClient, "query").mockResolvedValue({
      data: { InfrahubResourcePoolAllocated: { edges: [], count: 0 } },
    } as Awaited<ReturnType<typeof graphqlClient.query>>);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children);

    // WHEN
    await renderHook(
      () =>
        useGetResourceAllocated({ poolId: "pool-1", resourceId: "res-1", limit: 10, offset: 0 }),
      { wrapper }
    );

    // THEN
    await expect.poll(() => querySpy.mock.calls.length).toBe(1);
    expect(querySpy).toHaveBeenCalledWith(
      expect.objectContaining({ context: { branch: "feat-pool", date: null } })
    );
  });
});
