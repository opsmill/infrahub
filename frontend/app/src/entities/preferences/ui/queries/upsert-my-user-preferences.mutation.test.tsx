import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type React from "react";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { upsertMyUserPreference } from "@/entities/preferences/domain/use-cases/upsert-my-user-preference";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences-query.keys";
import { useUpdateMyUserPreferences } from "@/entities/preferences/ui/queries/upsert-my-user-preferences.mutation";

vi.mock("@/entities/preferences/domain/use-cases/upsert-my-user-preference");

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

describe("useUpdateMyUserPreferences", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("upserts the caller's own row and invalidates the effective key", async () => {
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

  test("forwards explicit null to reset a field", async () => {
    const { wrapper } = setup();
    vi.mocked(upsertMyUserPreference).mockResolvedValue();

    const { result } = await renderHook(() => useUpdateMyUserPreferences(), { wrapper });
    await result.current.mutateAsync({ dateFormat: null, timezone: null });

    expect(upsertMyUserPreference).toHaveBeenCalledWith({
      dateFormat: null,
      timezone: null,
    });
  });
});
