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

const openAccountMenu = async (page: Page) => {
  await page.getByTestId("unauthenticated-menu-trigger").click();
};

// No storageState: every test is a fresh anonymous visitor, which is both the coldest cache the
// pre-paint script can meet and the least privileged surface the switch must still be reachable on.
test.describe("theme", () => {
  test("a fresh visitor lands in dark when the deployment enables it", async ({ page }) => {
    await setDarkThemeFlag(page, true);

    await page.goto("/");
    await expect(page.getByTestId("sidebar")).toBeVisible();

    expect(await htmlTheme(page)).toBe("dark");

    await openAccountMenu(page);
    const switchItem = page.getByRole("menuitem", { name: "Light theme" });
    await expect(switchItem).toBeVisible();
    await expect(switchItem).toContainText("alpha");
  });

  test("switching to light applies instantly and survives a reload without flashing", async ({
    page,
  }) => {
    await setDarkThemeFlag(page, true);

    await page.goto("/");
    await expect(page.getByTestId("sidebar")).toBeVisible();

    await openAccountMenu(page);
    await page.getByRole("menuitem", { name: "Light theme" }).click();
    expect(await htmlTheme(page)).toBe("light");

    // The pre-paint script must deliver the choice before the app boots, so the document is
    // already light at the earliest observable moment of the next load.
    await page.goto("/", { waitUntil: "domcontentloaded" });
    expect(await htmlTheme(page)).toBe("light");

    await expect(page.getByTestId("sidebar")).toBeVisible();
    expect(await htmlTheme(page)).toBe("light");
  });

  test("a deployment with the theme off renders light and offers no switch", async ({ page }) => {
    await setDarkThemeFlag(page, false);

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
    expect(await htmlTheme(page)).toBe("light");

    await openAccountMenu(page);
    await expect(page.getByRole("menuitem", { name: "About Infrahub" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: /theme/i })).toHaveCount(0);

    // AND the stored choice is retained, never deleted: re-enabling the flag must restore it.
    expect(await page.evaluate(() => localStorage.getItem("infrahub.theme.choice"))).toBe("dark");
  });
});
