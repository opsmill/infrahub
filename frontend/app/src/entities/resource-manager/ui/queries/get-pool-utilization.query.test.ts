import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createStore, Provider } from "jotai";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { graphqlClient } from "@/shared/api/graphql/client";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useGetPoolUtilization } from "@/entities/resource-manager/ui/queries/get-pool-utilization.query";

import { generateBranch } from "../../../../../tests/fake/branch";

vi.mock("@/entities/branches/ui/branches-provider");

describe("useGetPoolUtilization", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("requests the pool utilization on the current branch", async () => {
    // GIVEN
    vi.mocked(useCurrentBranch).mockReturnValue({
      currentBranch: generateBranch({ name: "feat-pool" }),
    } as ReturnType<typeof useCurrentBranch>);
    const querySpy = vi.spyOn(graphqlClient, "query").mockResolvedValue({
      data: { InfrahubResourcePoolUtilization: { edges: [], count: 0 } },
    } as Awaited<ReturnType<typeof graphqlClient.query>>);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children);

    // WHEN
    await renderHook(() => useGetPoolUtilization({ poolId: "pool-1" }), { wrapper });

    // THEN
    await expect.poll(() => querySpy.mock.calls.length).toBe(1);
    expect(querySpy).toHaveBeenCalledWith(
      expect.objectContaining({ context: { branch: "feat-pool", date: null } })
    );
  });

  it("requests the pool utilization again after the branch and time-machine date change", async () => {
    // GIVEN
    vi.mocked(useCurrentBranch).mockReturnValue({
      currentBranch: generateBranch({ name: "feat-a" }),
    } as ReturnType<typeof useCurrentBranch>);
    const querySpy = vi.spyOn(graphqlClient, "query").mockResolvedValue({
      data: { InfrahubResourcePoolUtilization: { edges: [], count: 0 } },
    } as Awaited<ReturnType<typeof graphqlClient.query>>);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const store = createStore();
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(
        Provider,
        { store },
        React.createElement(QueryClientProvider, { client: queryClient }, children)
      );
    const { rerender } = await renderHook(() => useGetPoolUtilization({ poolId: "pool-1" }), {
      wrapper,
    });
    await expect.poll(() => querySpy.mock.calls.length).toBe(1);

    // WHEN
    const date = new Date("2026-01-15T10:00:00Z");
    vi.mocked(useCurrentBranch).mockReturnValue({
      currentBranch: generateBranch({ name: "feat-b" }),
    } as ReturnType<typeof useCurrentBranch>);
    store.set(datetimeAtom, date);
    await rerender();

    // THEN
    await expect.poll(() => querySpy.mock.calls.length).toBe(2);
    expect(querySpy).toHaveBeenLastCalledWith(
      expect.objectContaining({ context: { branch: "feat-b", date } })
    );
  });
});
