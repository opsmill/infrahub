import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";
import { abandonPush } from "@/entities/repository/domain/use-cases/abandon-push";
import { useAbandonPushMutation } from "@/entities/repository/ui/queries/abandon-push.mutation";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

import { generateBranch } from "../../../../../tests/fake/branch";

vi.mock("@/entities/branches/ui/queries/get-branches.query");
vi.mock("@/entities/repository/domain/use-cases/abandon-push");

const PUSH_STATE_KEY = repositoriesQueryKeys.pushState({ repositoryId: "repo-1" });
const ACTIVITY_KEY = repositoriesQueryKeys.activity({ repositoryId: "repo-1" });
const OTHER_REPOSITORY_KEY = repositoriesQueryKeys.pushState({ repositoryId: "repo-2" });
const SEEDED_KEYS = [PUSH_STATE_KEY, ACTIVITY_KEY, OTHER_REPOSITORY_KEY];

const renderMutation = async (onSettled = vi.fn()) => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  for (const queryKey of SEEDED_KEYS) queryClient.setQueryData(queryKey, {});

  const wrapper = ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
  const { result } = await renderHook(() => useAbandonPushMutation({ onSettled }), { wrapper });

  const invalidatedKeys = () =>
    SEEDED_KEYS.filter((queryKey) => queryClient.getQueryState(queryKey)?.isInvalidated);

  return { result, invalidatedKeys };
};

describe("useAbandonPushMutation", () => {
  beforeEach(() => {
    vi.resetAllMocks();

    vi.mocked(useGetBranches).mockReturnValue({
      data: [generateBranch({ name: "primary", is_default: true })],
    } as unknown as ReturnType<typeof useGetBranches>);
  });

  it("reloads the push state and the activity of the repository when the request is accepted", async () => {
    // GIVEN
    vi.mocked(abandonPush).mockResolvedValue({ ok: true, taskId: "task-1" });
    const onSettled = vi.fn();
    const { result, invalidatedKeys } = await renderMutation(onSettled);

    // WHEN
    await result.current.mutateAsync({ repositoryId: "repo-1", queueVersion: 4 });

    // THEN
    await vi.waitFor(() => expect(invalidatedKeys()).toEqual([PUSH_STATE_KEY, ACTIVITY_KEY]));
    expect(onSettled).toHaveBeenCalled();
  });

  it("reloads the push state and the activity of the repository when the request is refused", async () => {
    // GIVEN
    vi.mocked(abandonPush).mockRejectedValue(new Error("Nothing is pending."));
    const { result, invalidatedKeys } = await renderMutation();

    // WHEN
    await result.current.mutateAsync({ repositoryId: "repo-1", queueVersion: 4 }).catch(() => {});

    // THEN
    await vi.waitFor(() => expect(invalidatedKeys()).toEqual([PUSH_STATE_KEY, ACTIVITY_KEY]));
  });
});
