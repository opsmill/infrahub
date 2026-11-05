import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type React from "react";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { getConfigQueryOptions } from "@/entities/config/ui/queries/get-config.query";
import { updateGlobalPreference } from "@/entities/preferences/domain/use-cases/update-global-preference";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences.query-keys";
import { useUpdateGlobalPreferences } from "@/entities/preferences/ui/queries/update-global-preferences.mutation";

vi.mock("@/entities/preferences/domain/use-cases/update-global-preference");

const CONFIG_KEY = getConfigQueryOptions().queryKey;
const GLOBAL_PREFERENCES_KEY = preferencesQueryKeys.global();
const UNRELATED_KEY = ["branches"];
const SEEDED_KEYS = [CONFIG_KEY, GLOBAL_PREFERENCES_KEY, UNRELATED_KEY];

const renderMutation = async () => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  for (const queryKey of SEEDED_KEYS) queryClient.setQueryData(queryKey, {});

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  const { result } = await renderHook(() => useUpdateGlobalPreferences(), { wrapper });

  const invalidatedKeys = () =>
    SEEDED_KEYS.filter((queryKey) => queryClient.getQueryState(queryKey)?.isInvalidated);

  return { result, invalidatedKeys };
};

describe("useUpdateGlobalPreferences", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  test("reloads the config and the global preferences once the save succeeds", async () => {
    // GIVEN
    vi.mocked(updateGlobalPreference).mockResolvedValue();
    const { result, invalidatedKeys } = await renderMutation();

    // WHEN
    await result.current.mutateAsync({ instanceLabel: "QA" });

    // THEN
    await vi.waitFor(() => expect(invalidatedKeys()).toEqual([CONFIG_KEY, GLOBAL_PREFERENCES_KEY]));
  });

  test("keeps every query as it is when the save fails", async () => {
    // GIVEN
    vi.mocked(updateGlobalPreference).mockRejectedValue(new Error("Not allowed"));
    const { result, invalidatedKeys } = await renderMutation();

    // WHEN
    await result.current.mutateAsync({ instanceLabel: "QA" }).catch(() => {});

    // THEN
    expect(invalidatedKeys()).toEqual([]);
  });
});
