import { QueryClient, QueryObserver } from "@tanstack/react-query";
import { afterEach, describe, expect, test, vi } from "vitest";

import { clearSessionCache } from "@/entities/authentication/ui/queries/clear-session-cache";
import { getConfigQueryOptions } from "@/entities/config/ui/queries/get-config.query";

import { generateConfig } from "../../../../../tests/fake/config";

const USER_QUERY_KEY = ["user-data"];
const CONFIG = generateConfig();

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

afterEach(() => {
  queryClient.clear();
});

describe("clearSessionCache", () => {
  test("removes the previous session's data and mutations", async () => {
    // GIVEN
    queryClient.setQueryData(USER_QUERY_KEY, "previous user");
    await queryClient
      .getMutationCache()
      .build(queryClient, { mutationFn: async () => "saved" })
      .execute(undefined);

    // WHEN
    clearSessionCache(queryClient);

    // THEN
    expect(queryClient.getQueryData(USER_QUERY_KEY)).toBeUndefined();
    expect(queryClient.getMutationCache().getAll()).toHaveLength(0);
  });

  test("keeps the config data, which is the same for every user", () => {
    // GIVEN
    const { queryKey } = getConfigQueryOptions();
    queryClient.setQueryData(queryKey, CONFIG);

    // WHEN
    clearSessionCache(queryClient);

    // THEN
    expect(queryClient.getQueryData(queryKey)).toEqual(CONFIG);
  });

  test("keeps the observed config query, so invalidating it refetches the config", async () => {
    // GIVEN
    const { queryKey } = getConfigQueryOptions();
    const queryFn = vi.fn().mockResolvedValue(CONFIG);
    const observer = new QueryObserver(queryClient, { queryKey, queryFn });
    const unsubscribe = observer.subscribe(() => {});
    try {
      await vi.waitFor(() => expect(observer.getCurrentResult().isSuccess).toBe(true));
      clearSessionCache(queryClient);

      // WHEN
      await queryClient.invalidateQueries({ queryKey });

      // THEN
      expect(queryFn).toHaveBeenCalledTimes(2);
    } finally {
      unsubscribe();
    }
  });
});
