import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type React from "react";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { resetMyUserPreference } from "@/entities/preferences/domain/reset-my-user-preference";
import { updateGlobalPreference } from "@/entities/preferences/domain/update-global-preference";
import { upsertMyUserPreference } from "@/entities/preferences/domain/upsert-my-user-preference";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences-query.keys";
import { useResetMyUserPreferences } from "@/entities/preferences/ui/queries/reset-my-user-preferences.mutation";
import { useUpdateGlobalPreferences } from "@/entities/preferences/ui/queries/update-global-preferences.mutation";
import { useUpsertMyUserPreferences } from "@/entities/preferences/ui/queries/upsert-my-user-preferences.mutation";

vi.mock("@/entities/preferences/domain/upsert-my-user-preference");
vi.mock("@/entities/preferences/domain/update-global-preference");
vi.mock("@/entities/preferences/domain/reset-my-user-preference");
vi.mock("@/entities/authentication/ui/useAuth", () => ({
  useAuth: () => ({
    accessToken: "",
    isAuthenticated: true,
    setToken: () => {},
    user: { id: "account-1" },
  }),
}));

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

  test("useUpsertMyUserPreferences builds the lazy payload from the session account and invalidates the effective + user keys", async () => {
    const { invalidateSpy, wrapper } = setup();
    vi.mocked(upsertMyUserPreference).mockResolvedValue();

    const { result } = await renderHook(() => useUpsertMyUserPreferences(), { wrapper });
    await result.current.mutateAsync({ dateFormat: "relative", timezone: "UTC" });

    expect(upsertMyUserPreference).toHaveBeenCalledWith({
      accountId: "account-1",
      dateFormat: "relative",
      timezone: "UTC",
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: preferencesQueryKeys.effective(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: preferencesQueryKeys.user("account-1"),
    });
  });

  test("useUpdateGlobalPreferences invalidates the effective + global keys", async () => {
    const { invalidateSpy, wrapper } = setup();
    vi.mocked(updateGlobalPreference).mockResolvedValue();

    const { result } = await renderHook(() => useUpdateGlobalPreferences(), { wrapper });
    await result.current.mutateAsync({
      id: "global-1",
      dateFormat: "dd/MM/yyyy",
      timezone: "Europe/Paris",
    });

    expect(vi.mocked(updateGlobalPreference).mock.calls[0]?.[0]).toEqual({
      id: "global-1",
      dateFormat: "dd/MM/yyyy",
      timezone: "Europe/Paris",
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: preferencesQueryKeys.effective(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: preferencesQueryKeys.global(),
    });
  });

  test("useResetMyUserPreferences deletes the override row and invalidates the effective + user keys", async () => {
    const { invalidateSpy, wrapper } = setup();
    vi.mocked(resetMyUserPreference).mockResolvedValue();

    const { result } = await renderHook(() => useResetMyUserPreferences(), { wrapper });
    await result.current.mutateAsync({ id: "user-pref-1" });

    expect(vi.mocked(resetMyUserPreference).mock.calls[0]?.[0]).toEqual({ id: "user-pref-1" });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: preferencesQueryKeys.effective(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: preferencesQueryKeys.user("account-1"),
    });
  });
});
