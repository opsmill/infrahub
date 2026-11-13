import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { ResolvedTheme } from "@/entities/config/domain/model/theme";
import { ThemeProvider, useTheme } from "@/entities/config/ui/theme-provider";

import indexHtml from "../../../../index.html?raw";
import { render } from "../../../../tests/components/render";

const Probe = () => {
  const { theme, resolvedTheme, setTheme } = useTheme();

  return (
    <>
      <span data-testid="theme">{theme}</span>
      <span data-testid="resolved-theme">{resolvedTheme}</span>
      <span data-testid="transition" style={{ transition: "color 1s" }} />
      <button type="button" onClick={() => setTheme("dark")}>
        go dark
      </button>
    </>
  );
};

const isDark = () => document.documentElement.classList.contains("dark");

function mockSystemTheme(systemTheme: ResolvedTheme) {
  const listeners = new Set<() => void>();
  let matches = systemTheme === "dark";
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

  return (nextSystemTheme: ResolvedTheme) => {
    matches = nextSystemTheme === "dark";
    listeners.forEach((listener) => listener());
  };
}

function runPrePaintScript() {
  const script = document.createElement("script");
  script.textContent = indexHtml.match(/<script>([\s\S]*?)<\/script>/)?.[1] ?? "";
  document.head.append(script);
}

describe("ThemeProvider", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    document.documentElement.classList.remove("dark");
  });

  test("follows the desktop for a visitor who never chose", async () => {
    // GIVEN
    mockSystemTheme("dark");

    // WHEN
    const component = await render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>
    );

    // THEN
    await expect.element(component.getByTestId("theme")).toHaveTextContent("system");
    await expect.element(component.getByTestId("resolved-theme")).toHaveTextContent("dark");
    expect(isDark()).toBe(true);
  });

  test("tracks a desktop that changes appearance while the page is open", async () => {
    // GIVEN
    const setSystemTheme = mockSystemTheme("light");
    await render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>
    );
    expect(isDark()).toBe(false);

    // WHEN
    setSystemTheme("dark");

    // THEN
    await expect.poll(isDark).toBe(true);
  });

  test("prefers an explicit choice over the desktop", async () => {
    // GIVEN
    mockSystemTheme("dark");
    localStorage.setItem("infrahub.theme.choice", "light");

    // WHEN
    const component = await render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>
    );

    // THEN
    await expect.element(component.getByTestId("resolved-theme")).toHaveTextContent("light");
    expect(isDark()).toBe(false);
  });

  test("persists a choice and paints it", async () => {
    // GIVEN
    mockSystemTheme("light");
    const component = await render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>
    );

    // WHEN
    await component.getByRole("button", { name: "go dark" }).click();

    // THEN
    await expect.poll(isDark).toBe(true);
    expect(localStorage.getItem("infrahub.theme.choice")).toBe("dark");
  });

  test("lets transitions run again once the palette has switched", async () => {
    // GIVEN
    mockSystemTheme("light");
    const component = await render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>
    );

    // WHEN
    await component.getByRole("button", { name: "go dark" }).click();

    // THEN
    await expect.poll(isDark).toBe(true);
    const probe = component.getByTestId("transition").element();
    await expect.poll(() => getComputedStyle(probe).transitionProperty).toBe("color");
  });

  test("picks up a choice made in another tab", async () => {
    // GIVEN
    mockSystemTheme("light");
    const component = await render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>
    );

    // WHEN
    localStorage.setItem("infrahub.theme.choice", "dark");
    window.dispatchEvent(new StorageEvent("storage", { key: "infrahub.theme.choice" }));

    // THEN
    await expect.element(component.getByTestId("theme")).toHaveTextContent("dark");
    expect(isDark()).toBe(true);
  });

  test("falls back to system when another tab clears storage", async () => {
    // GIVEN
    mockSystemTheme("light");
    localStorage.setItem("infrahub.theme.choice", "dark");
    const component = await render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>
    );
    await expect.element(component.getByTestId("theme")).toHaveTextContent("dark");

    // WHEN
    localStorage.clear();
    window.dispatchEvent(new StorageEvent("storage", { key: null }));

    // THEN
    await expect.element(component.getByTestId("theme")).toHaveTextContent("system");
    expect(isDark()).toBe(false);
  });

  test("still applies a choice when the browser blocks storage", async () => {
    // GIVEN
    mockSystemTheme("light");
    const blocked = () => {
      throw new DOMException("Site data is blocked", "SecurityError");
    };
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(blocked);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(blocked);
    const component = await render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>
    );
    await expect.element(component.getByTestId("theme")).toHaveTextContent("system");

    // WHEN
    await component.getByRole("button", { name: "go dark" }).click();

    // THEN
    await expect.element(component.getByTestId("theme")).toHaveTextContent("dark");
    expect(isDark()).toBe(true);
  });

  test("ignores a stored value that is not a theme", async () => {
    // GIVEN
    mockSystemTheme("light");
    localStorage.setItem("infrahub.theme.choice", "sepia");

    // WHEN
    const component = await render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>
    );

    // THEN
    await expect.element(component.getByTestId("theme")).toHaveTextContent("system");
  });

  test.each([
    { stored: "light", systemTheme: "dark", paintsDark: false },
    { stored: "dark", systemTheme: "light", paintsDark: true },
    { stored: "system", systemTheme: "dark", paintsDark: true },
  ] as const)(
    "index.html for a stored $stored on a $systemTheme system, paints dark: $paintsDark",
    ({ stored, systemTheme, paintsDark }) => {
      // GIVEN
      mockSystemTheme(systemTheme);
      localStorage.setItem("infrahub.theme.choice", stored);

      // WHEN
      runPrePaintScript();

      // THEN
      expect(isDark()).toBe(paintsDark);
    }
  );

  test("index.html follows the system theme when storage is blocked", () => {
    // GIVEN
    mockSystemTheme("dark");
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("Site data is blocked", "SecurityError");
    });

    // WHEN
    runPrePaintScript();

    // THEN
    expect(isDark()).toBe(true);
  });
});
