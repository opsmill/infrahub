import { QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { queryClient } from "@/shared/api/rest/client";

import { getConfigQueryOptions } from "@/entities/config/ui/queries/get-config.query";
import { updateGlobalPreference } from "@/entities/preferences/domain/use-cases/update-global-preference";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences.query-keys";
import { useUpdateGlobalPreferences } from "@/entities/preferences/ui/queries/update-global-preferences.mutation";

vi.mock("@/entities/preferences/domain/use-cases/update-global-preference");

const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(QueryClientProvider, { client: queryClient }, children);

afterEach(() => {
  vi.restoreAllMocks();
  queryClient.clear();
});

describe("useUpdateGlobalPreferences", () => {
  test("invalidates the preferences and the config once the save succeeds", async () => {
    // GIVEN
    vi.mocked(updateGlobalPreference).mockResolvedValue();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = await renderHook(() => useUpdateGlobalPreferences(), { wrapper });

    // WHEN
    await result.current.mutateAsync({ instanceLabel: "QA" });

    // THEN
    await expect
      .poll(() => invalidateSpy)
      .toHaveBeenCalledWith({ queryKey: getConfigQueryOptions().queryKey });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: preferencesQueryKeys.all() });
  });

  test("invalidates nothing when the save fails", async () => {
    // GIVEN
    vi.mocked(updateGlobalPreference).mockRejectedValue(new Error("Not allowed"));
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = await renderHook(() => useUpdateGlobalPreferences(), { wrapper });

    // WHEN
    await expect(result.current.mutateAsync({ instanceLabel: "QA" })).rejects.toThrow(
      "Not allowed"
    );

    // THEN
    expect(invalidateSpy).not.toHaveBeenCalled();
  });
});
