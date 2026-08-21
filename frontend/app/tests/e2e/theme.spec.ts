import { expect, type Page, test } from "@playwright/test";

const setDarkThemeFlag = (page: Page, enabled: boolean) =>
  page.route("*/**/api/config", async (route) => {
    const response = await route.fetch();
    const json = await response.json();
    await route.fulfill({
      json: {
        ...json,
        experimental_features: { ...json.experimental_features, dark_theme: enabled },
      },
    });
  });

const htmlTheme = (page: Page) =>
  page.evaluate(() => (document.documentElement.classList.contains("dark") ? "dark" : "light"));

// Retries. The class lands in a layout effect, so it is applied in the same commit the markup
// arrives in, but a visibility wait can still return between the two. Use this everywhere except
// the earliest-observable checks below, which must sample once to mean anything.
const expectHtmlTheme = (page: Page, expected: "dark" | "light") =>
  expect.poll(() => htmlTheme(page)).toBe(expected);

const openAccountMenu = async (page: Page) => {
  await page.getByTestId("unauthenticated-menu-trigger").click();
};

// No storageState: every test is a fresh anonymous visitor, which is both the coldest cache the
// pre-paint script can meet and the least privileged surface the switch must still be reachable on.
//
// These need a built frontend, which is what the docker stack serves. A Vite dev server overrides
// the default to dark so that whoever is working on the theme has it on screen, and pointing
// INFRAHUB_ADDRESS at one would fail the two desktop-following tests for that reason alone.
test.describe("theme", () => {
  test("a fresh visitor on a dark desktop lands in dark when the deployment enables it", async ({
    page,
  }) => {
    await setDarkThemeFlag(page, true);
    await page.emulateMedia({ colorScheme: "dark" });

    await page.goto("/");
    await expect(page.getByTestId("sidebar")).toBeVisible();

    await expectHtmlTheme(page, "dark");

    await openAccountMenu(page);
    // Offers the way back out, untagged — only the step *into* the pre-release theme is tagged.
    const switchItem = page.getByRole("menuitem", { name: "Light theme" });
    await expect(switchItem).toBeVisible();
    await expect(switchItem).not.toContainText("alpha");
  });

  test("a fresh visitor on a light desktop stays light, and is offered the way in", async ({
    page,
  }) => {
    await setDarkThemeFlag(page, true);
    await page.emulateMedia({ colorScheme: "light" });

    await page.goto("/");
    await expect(page.getByTestId("sidebar")).toBeVisible();

    await expectHtmlTheme(page, "light");

    await openAccountMenu(page);
    await expect(page.getByRole("menuitem", { name: "Dark theme" })).toContainText("alpha");
  });

  test("switching to light applies instantly and survives a reload without flashing", async ({
    page,
  }) => {
    await setDarkThemeFlag(page, true);
    await page.emulateMedia({ colorScheme: "dark" });

    await page.goto("/");
    await expect(page.getByTestId("sidebar")).toBeVisible();

    await openAccountMenu(page);
    await page.getByRole("menuitem", { name: "Light theme" }).click();
    await expectHtmlTheme(page, "light");

    // The pre-paint script must deliver the choice before the app boots, so the document is
    // already light at the earliest observable moment of the next load — on a desktop still asking
    // for dark, which is what makes this a test of the choice rather than of the default. Sampled
    // once on purpose: retrying here would also accept the class arriving later from React, which
    // is the very regression this asserts against.
    await page.goto("/", { waitUntil: "domcontentloaded" });
    expect(await htmlTheme(page)).toBe("light");

    await expect(page.getByTestId("sidebar")).toBeVisible();
    await expectHtmlTheme(page, "light");

    await openAccountMenu(page);
    await expect(page.getByRole("menuitem", { name: "Dark theme" })).toContainText("alpha");
  });

  test("a deployment with the theme off renders light and offers no switch", async ({ page }) => {
    await setDarkThemeFlag(page, false);
    // On a desktop asking for dark: the operating system expresses a preference, not a permission,
    // and must not reach past an operator who turned the theme off.
    await page.emulateMedia({ colorScheme: "dark" });

    // GIVEN a user who chose dark while the feature was on, after one visit has re-mirrored the
    // resolved theme (the first load after the flag flips may still paint one stale dark frame;
    // the mirror is what heals it)
    await page.goto("/");
    await page.evaluate(() => {
      localStorage.setItem("infrahub.theme.choice", "dark");
      localStorage.setItem("infrahub.theme.resolved", "light");
    });

    await page.goto("/", { waitUntil: "domcontentloaded" });
    expect(await htmlTheme(page)).toBe("light");

    await expect(page.getByTestId("sidebar")).toBeVisible();
    await expectHtmlTheme(page, "light");

    await openAccountMenu(page);
    await expect(page.getByRole("menuitem", { name: "About Infrahub" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: /theme/i })).toHaveCount(0);

    // AND the stored choice is retained, never deleted: re-enabling the flag must restore it.
    expect(await page.evaluate(() => localStorage.getItem("infrahub.theme.choice"))).toBe("dark");
  });
});
