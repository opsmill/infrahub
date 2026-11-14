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

  test("refreshes the config when only the color is saved", async () => {
    // GIVEN
    vi.mocked(updateGlobalPreference).mockResolvedValue();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = await renderHook(() => useUpdateGlobalPreferences(), { wrapper });

    // WHEN
    await result.current.mutateAsync({ instanceColor: "RED" });

    // THEN
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: getConfigQueryOptions().queryKey });
  });

  test("leaves the config alone when only the date and time defaults are saved", async () => {
    // GIVEN
    vi.mocked(updateGlobalPreference).mockResolvedValue();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = await renderHook(() => useUpdateGlobalPreferences(), { wrapper });

    // WHEN
    await result.current.mutateAsync({ dateFormat: "ISO_DATETIME", timezone: "UTC" });

    // THEN
    expect(invalidateSpy.mock.calls).toStrictEqual([[{ queryKey: preferencesQueryKeys.all() }]]);
  });

  test("resolves the save only once the refetches have finished", async () => {
    // GIVEN
    vi.mocked(updateGlobalPreference).mockResolvedValue();
    let finishRefetch = () => {};
    const refetch = new Promise<void>((resolve) => {
      finishRefetch = resolve;
    });
    vi.spyOn(queryClient, "invalidateQueries").mockReturnValue(refetch);
    const { result } = await renderHook(() => useUpdateGlobalPreferences(), { wrapper });
    let saved = false;

    // WHEN
    const save = result.current.mutateAsync({ instanceLabel: "QA" }).then(() => {
      saved = true;
    });
    await expect.poll(() => vi.mocked(queryClient.invalidateQueries).mock.calls.length).toBe(2);

    // THEN
    expect(saved).toBe(false);
    finishRefetch();
    await save;
    expect(saved).toBe(true);
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
