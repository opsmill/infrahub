import { describe, expect, it, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import type { Config } from "@/entities/config/domain/model/config";
import { useConfig } from "@/entities/config/ui/config-provider";
import { useFeatureFlag } from "@/entities/config/ui/hooks/use-feature-flag";

vi.mock("@/entities/config/ui/config-provider");

describe("useFeatureFlag", () => {
  const useConfigMock = vi.mocked(useConfig);

  it("returns true when the backend enables the flag", async () => {
    // GIVEN
    useConfigMock.mockReturnValue({ experimental_features: { dark_theme: true } } as Config);

    // WHEN
    const { result } = await renderHook(() => useFeatureFlag("dark_theme"));

    // THEN
    expect(result.current).toBe(true);
  });

  it("returns false when the backend disables the flag", async () => {
    // GIVEN
    useConfigMock.mockReturnValue({ experimental_features: { dark_theme: false } } as Config);

    // WHEN
    const { result } = await renderHook(() => useFeatureFlag("dark_theme"));

    // THEN
    expect(result.current).toBe(false);
  });

  it("returns false when the backend predates the flag and does not report it", async () => {
    // GIVEN
    useConfigMock.mockReturnValue({ experimental_features: {} } as Config);

    // WHEN
    const { result } = await renderHook(() => useFeatureFlag("dark_theme"));

    // THEN
    expect(result.current).toBe(false);
  });

  it("reads only the flag it is asked for", async () => {
    // GIVEN
    useConfigMock.mockReturnValue({ experimental_features: { dark_theme: true } } as Config);

    // WHEN
    const { result } = await renderHook(() => useFeatureFlag("graphql_enums"));

    // THEN
    expect(result.current).toBe(false);
  });
});
