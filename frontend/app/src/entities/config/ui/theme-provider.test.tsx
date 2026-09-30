import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { Config } from "@/entities/config/domain/model/config";
import { ConfigContext } from "@/entities/config/ui/config-provider";
import { ThemeProvider, useTheme } from "@/entities/config/ui/theme-provider";

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

const withFlag = (darkTheme: boolean) => (
  <ConfigContext value={{ experimental_features: { dark_theme: darkTheme } } as Config}>
    <ThemeProvider>
      <Probe />
    </ThemeProvider>
  </ConfigContext>
);

const isDark = () => document.documentElement.classList.contains("dark");

function mockDesktop(prefersDark: boolean) {
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

  return (nextPrefersDark: boolean) => {
    matches = nextPrefersDark;
    listeners.forEach((listener) => listener());
  };
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
    mockDesktop(true);

    // WHEN
    const component = await render(withFlag(true));

    // THEN
    await expect.element(component.getByTestId("theme")).toHaveTextContent("system");
    await expect.element(component.getByTestId("resolved-theme")).toHaveTextContent("dark");
    expect(isDark()).toBe(true);
  });

  test("tracks a desktop that changes appearance while the page is open", async () => {
    // GIVEN
    const setDesktop = mockDesktop(false);
    await render(withFlag(true));
    expect(isDark()).toBe(false);

    // WHEN
    setDesktop(true);

    // THEN
    await expect.poll(isDark).toBe(true);
  });

  test("prefers an explicit choice over the desktop", async () => {
    // GIVEN
    mockDesktop(true);
    localStorage.setItem("infrahub.theme.choice", "light");

    // WHEN
    const component = await render(withFlag(true));

    // THEN
    await expect.element(component.getByTestId("resolved-theme")).toHaveTextContent("light");
    expect(isDark()).toBe(false);
  });

  test("persists a choice and paints it", async () => {
    // GIVEN
    mockDesktop(false);
    const component = await render(withFlag(true));

    // WHEN
    await component.getByRole("button", { name: "go dark" }).click();

    // THEN
    await expect.poll(isDark).toBe(true);
    expect(localStorage.getItem("infrahub.theme.choice")).toBe("dark");
  });

  test("lets transitions run again once the palette has switched", async () => {
    // GIVEN
    mockDesktop(false);
    const component = await render(withFlag(true));

    // WHEN
    await component.getByRole("button", { name: "go dark" }).click();

    // THEN
    await expect.poll(isDark).toBe(true);
    const probe = component.getByTestId("transition").element();
    await expect.poll(() => getComputedStyle(probe).transitionProperty).toBe("color");
  });

  test("forces light without touching the stored choice when the deployment disables dark", async () => {
    // GIVEN
    localStorage.setItem("infrahub.theme.choice", "dark");

    // WHEN
    const component = await render(withFlag(false));

    // THEN
    await expect.element(component.getByTestId("resolved-theme")).toHaveTextContent("light");
    expect(isDark()).toBe(false);
    expect(localStorage.getItem("infrahub.theme.choice")).toBe("dark");
  });

  test("restores the stored choice when the deployment enables dark again", async () => {
    // GIVEN
    mockDesktop(false);
    localStorage.setItem("infrahub.theme.choice", "dark");
    const component = await render(withFlag(false));
    expect(isDark()).toBe(false);

    // WHEN
    await component.rerender(withFlag(true));

    // THEN
    await expect.element(component.getByTestId("theme")).toHaveTextContent("dark");
    expect(isDark()).toBe(true);
  });

  test("picks up a choice made in another tab", async () => {
    // GIVEN
    mockDesktop(false);
    const component = await render(withFlag(true));

    // WHEN
    localStorage.setItem("infrahub.theme.choice", "dark");
    window.dispatchEvent(new StorageEvent("storage", { key: "infrahub.theme.choice" }));

    // THEN
    await expect.element(component.getByTestId("theme")).toHaveTextContent("dark");
    expect(isDark()).toBe(true);
  });

  test("ignores a stored value that is not a theme", async () => {
    // GIVEN
    mockDesktop(false);
    localStorage.setItem("infrahub.theme.choice", "sepia");

    // WHEN
    const component = await render(withFlag(true));

    // THEN
    await expect.element(component.getByTestId("theme")).toHaveTextContent("system");
  });
});
