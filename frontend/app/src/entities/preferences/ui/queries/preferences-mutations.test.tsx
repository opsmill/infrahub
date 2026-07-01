import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type React from "react";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { updateGlobalPreference } from "@/entities/preferences/domain/update-global-preference";
import { upsertMyUserPreference } from "@/entities/preferences/domain/upsert-my-user-preference";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences-query.keys";
import { useUpdateGlobalPreferences } from "@/entities/preferences/ui/queries/update-global-preferences.mutation";
import { useUpdateMyUserPreferences } from "@/entities/preferences/ui/queries/upsert-my-user-preferences.mutation";

vi.mock("@/entities/preferences/domain/upsert-my-user-preference");
vi.mock("@/entities/preferences/domain/update-global-preference");

function setup() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { invalidateSpy, wrapper };
}

describe("preferences mutations", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("useUpdateMyUserPreferences upserts the caller's own row and invalidates the effective key", async () => {
    const { invalidateSpy, wrapper } = setup();
    vi.mocked(upsertMyUserPreference).mockResolvedValue();

    const { result } = await renderHook(() => useUpdateMyUserPreferences(), { wrapper });
    await result.current.mutateAsync({ dateFormat: "ISO_DATETIME", timezone: "UTC" });

    expect(upsertMyUserPreference).toHaveBeenCalledWith({
      dateFormat: "ISO_DATETIME",
      timezone: "UTC",
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: preferencesQueryKeys.effective(),
    });
  });

  test("useUpdateMyUserPreferences forwards explicit null to reset a field", async () => {
    const { wrapper } = setup();
    vi.mocked(upsertMyUserPreference).mockResolvedValue();

    const { result } = await renderHook(() => useUpdateMyUserPreferences(), { wrapper });
    await result.current.mutateAsync({ dateFormat: null, timezone: null });

    expect(upsertMyUserPreference).toHaveBeenCalledWith({
      dateFormat: null,
      timezone: null,
    });
  });

  test("useUpdateGlobalPreferences updates the org defaults and invalidates the effective and global keys", async () => {
    const { invalidateSpy, wrapper } = setup();
    vi.mocked(updateGlobalPreference).mockResolvedValue();

    const { result } = await renderHook(() => useUpdateGlobalPreferences(), { wrapper });
    await result.current.mutateAsync({
      dateFormat: "EU_DATETIME",
      timezone: "Europe/Paris",
    });

    expect(vi.mocked(updateGlobalPreference).mock.calls[0]?.[0]).toEqual({
      dateFormat: "EU_DATETIME",
      timezone: "Europe/Paris",
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: preferencesQueryKeys.effective(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: preferencesQueryKeys.global(),
    });
  });
});
