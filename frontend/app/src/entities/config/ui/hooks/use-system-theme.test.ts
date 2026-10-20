import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { useSystemTheme } from "@/entities/config/ui/hooks/use-system-theme";

function mockSystemTheme(prefersDark: boolean) {
  const listeners = new Set<() => void>();
  let matches = prefersDark;
  vi.spyOn(window, "matchMedia").mockImplementation(
    (query) =>
      ({
        media: query,
        get matches() {
          return matches;
        },
        addEventListener: (_: string, listener: () => void) => listeners.add(listener),
        removeEventListener: (_: string, listener: () => void) => listeners.delete(listener),
      }) as unknown as MediaQueryList
  );

  return {
    listeners,
    setPrefersDark: (nextPrefersDark: boolean) => {
      matches = nextPrefersDark;
      listeners.forEach((listener) => listener());
    },
  };
}

describe("useSystemTheme", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns light when the OS prefers a light scheme", async () => {
    // GIVEN
    mockSystemTheme(false);

    // WHEN
    const { result } = await renderHook(() => useSystemTheme());

    // THEN
    expect(result.current).toBe("light");
  });

  it("returns dark when the OS prefers a dark scheme", async () => {
    // GIVEN
    mockSystemTheme(true);

    // WHEN
    const { result } = await renderHook(() => useSystemTheme());

    // THEN
    expect(result.current).toBe("dark");
  });

  it("follows the OS when its preferred scheme changes", async () => {
    // GIVEN
    const { setPrefersDark } = mockSystemTheme(false);
    const { result } = await renderHook(() => useSystemTheme());

    // WHEN
    setPrefersDark(true);

    // THEN
    await expect.poll(() => result.current).toBe("dark");
  });

  it("stops listening to the OS once unmounted", async () => {
    // GIVEN
    const { listeners } = mockSystemTheme(false);
    const { unmount } = await renderHook(() => useSystemTheme());

    // WHEN
    await unmount();

    // THEN
    expect(listeners.size).toBe(0);
  });
});
