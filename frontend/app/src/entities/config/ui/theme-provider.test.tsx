import { useThemeControl } from "@infrahub/ui";
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import type { Config } from "@/entities/config/domain/model/config";
import { ConfigContext } from "@/entities/config/ui/config-provider";
import { ThemeProvider } from "@/entities/config/ui/theme-provider";

import { render } from "../../../../tests/components/render";

const configWithFlag = (darkTheme: boolean) =>
  ({ experimental_features: { dark_theme: darkTheme } }) as Config;

const Probe = () => {
  const { canChoose, setTheme } = useThemeControl();

  return (
    <>
      <span data-testid="can-choose">{String(canChoose)}</span>
      <button type="button" onClick={() => setTheme("light")}>
        go light
      </button>
      <button type="button" onClick={() => setTheme("dark")}>
        go dark
      </button>
    </>
  );
};

function renderWithFlag(darkTheme: boolean) {
  return render(
    <ConfigContext value={configWithFlag(darkTheme)}>
      <ThemeProvider>
        <Probe />
      </ThemeProvider>
    </ConfigContext>
  );
}

const isDark = () => document.documentElement.classList.contains("dark");
const systemPrefersDark = () => window.matchMedia("(prefers-color-scheme: dark)").matches;

describe("ThemeProvider", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
  });

  afterEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
  });

  // Vitest serves the app through Vite in dev mode, so import.meta.env.DEV is true for every test
  // in this file and the dev-server override is the only branch reachable here. The desktop
  // follows the desktop in getDefaultTheme's own test and in the E2E suite, which runs a build.
  test("defaults to dark under a dev server, whatever the desktop asks for", async () => {
    // Stated rather than assumed: dark below means the override fired, not that the harness
    // happens to report a dark desktop.
    expect(systemPrefersDark()).toBe(false);

    const component = await renderWithFlag(true);

    await expect.element(component.getByTestId("can-choose")).toHaveTextContent("true");
    expect(isDark()).toBe(true);
  });

  test("stays light when the deployment does not enable the theme", async () => {
    const component = await renderWithFlag(false);

    await expect.element(component.getByTestId("can-choose")).toHaveTextContent("false");
    expect(isDark()).toBe(false);
  });

  test("mirrors whatever it resolved, so the next load paints before the config returns", async () => {
    await renderWithFlag(true);

    await expect.poll(() => localStorage.getItem("infrahub.theme.resolved")).toBe("dark");
  });

  test("a chosen theme overrides the default and survives a remount", async () => {
    const first = await renderWithFlag(true);
    await first.getByRole("button", { name: "go light" }).click();

    await expect.poll(isDark).toBe(false);

    first.unmount();
    document.documentElement.classList.remove("dark");

    await renderWithFlag(true);

    await expect.poll(isDark).toBe(false);
  });

  test("ignores a stored choice, without deleting it, once the theme is turned off", async () => {
    // GIVEN a user who chose dark while the feature was enabled
    localStorage.setItem("infrahub.theme.choice", "dark");

    // WHEN an operator disables it
    const component = await renderWithFlag(false);

    await expect.element(component.getByTestId("can-choose")).toHaveTextContent("false");
    await expect.poll(isDark).toBe(false);

    // THEN their choice is left alone. Turning off a flag is a decision about a deployment and
    // must not reach through and destroy what users picked.
    expect(localStorage.getItem("infrahub.theme.choice")).toBe("dark");
  });

  test("honours a stored choice again when the theme comes back", async () => {
    localStorage.setItem("infrahub.theme.choice", "light");

    await renderWithFlag(true);

    await expect.poll(isDark).toBe(false);
  });
});
