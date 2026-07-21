import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/profile", () => {
  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test.describe("when not logged in", () => {
    test("should see 'Login' and no user avatar on header", async ({ page }) => {
      await page.goto("/");

      await expect(page.getByTestId("unauthenticated-menu-trigger")).toBeVisible();
      await expect(page.getByTestId("authenticated-menu-trigger")).toBeHidden();
    });
  });

  test.describe("when logged in as admin account", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should access the profile page", async ({ page }) => {
      await test.step("go to profile page", async () => {
        await page.goto("/");
        await page.getByTestId("authenticated-menu-trigger").click();
        await page.getByRole("menuitem", { name: "Account settings" }).click();
      });

      await test.step("display account details", async () => {
        await expect(page.getByRole("heading", { name: "Admin", exact: true })).toBeVisible();
        await expect(page.getByText("Nameadmin")).toBeVisible();
        await expect(page.getByText("LabelAdmin")).toBeVisible();
      });
    });

    test("should access the global preferences page from the account menu", async ({ page }) => {
      await test.step("open global preferences from the account menu", async () => {
        await page.goto("/");
        await page.getByTestId("authenticated-menu-trigger").click();
        await page.getByRole("menuitem", { name: "Global preferences" }).click();
      });

      await test.step("display the global preferences page", async () => {
        await expect(page).toHaveURL(/\/global-preferences/);
        await expect(page.getByRole("heading", { name: "Global preferences" })).toBeVisible();
        await expect(page.getByText("Global date and time")).toBeVisible();
        await expect(page.getByRole("link", { name: "Tokens" })).toBeHidden();
      });
    });

    test("should redirect the legacy profile URL to the global preferences page", async ({
      page,
    }) => {
      await page.goto("/profile/global-preferences");

      await expect(page).toHaveURL(/\/global-preferences/);
      await expect(page).not.toHaveURL(/\/profile/);
    });
  });

  test.describe("when logged in as read-write account", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.READ_WRITE });

    test("should access the profile page", async ({ page }) => {
      await test.step("go to profile page", async () => {
        await page.goto("/");
        await page.getByTestId("authenticated-menu-trigger").click();
        await page.getByRole("menuitem", { name: "Account settings" }).click();
      });

      await test.step("display account details", async () => {
        await expect(
          page.getByRole("heading", { name: "Chloe O'Brian", exact: true })
        ).toBeVisible();
        await expect(page.getByText("LabelChloe O'Brian")).toBeVisible();
      });
    });
  });

  test.describe("when logged in as read-only account", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.READ_ONLY });

    test("should access the profile page", async ({ page }) => {
      await test.step("go to profile page", async () => {
        await page.goto("/");
        await page.getByTestId("authenticated-menu-trigger").click();
        await page.getByRole("menuitem", { name: "Account settings" }).click();
      });

      await test.step("display account details", async () => {
        await expect(page.getByRole("heading", { name: "Jack Bauer", exact: true })).toBeVisible();
        await expect(page.getByText("LabelJack Bauer")).toBeVisible();
      });
    });

    test("should not access global preferences", async ({ page }) => {
      await test.step("hide the menu item", async () => {
        await page.goto("/");
        await page.getByTestId("authenticated-menu-trigger").click();

        await expect(page.getByRole("menuitem", { name: "Account settings" })).toBeVisible();
        await expect(page.getByRole("menuitem", { name: "Global preferences" })).toBeHidden();
      });

      await test.step("show the unauthorized screen on direct navigation", async () => {
        await page.goto("/global-preferences");

        // The custom message sits inside the unauthorized screen's collapsed accordion.
        await page.getByText("You can't access this view").click();
        await expect(
          page.getByText("You don't have permission to edit global preferences")
        ).toBeVisible();
      });
    });
  });
});
