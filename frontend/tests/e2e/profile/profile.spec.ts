import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/profile", () => {
  test.describe("when not logged in", () => {
    test("should see 'Sign in' and no user avatar on header", async ({ page }) => {
      await page.goto("/");

      await expect(page.getByRole("link", { name: "Sign in" })).toBeVisible();
      await expect(page.getByTestId("current-user-avatar-button")).toBeHidden();
    });
  });

  test.describe("when logged in as admin account", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should access the profile page", async ({ page }) => {
      await test.step("go to profile page", async () => {
        await page.goto("/");
        await page.getByTestId("current-user-avatar-button").click();
        await page.getByRole("menuitem", { name: "Your Profile" }).click();
      });

      await test.step("display account details", async () => {
        await expect(page.getByRole("heading", { name: "Admin", exact: true })).toBeVisible();
        await expect(page.getByText("Nameadmin")).toBeVisible();
        await expect(page.getByText("LabelAdmin")).toBeVisible();
        await expect(page.getByText("Roleadmin")).toBeVisible();
      });
    });
  });

  test.describe("when logged in as read-write account", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.READ_WRITE });

    test("should access the profile page", async ({ page }) => {
      await test.step("go to profile page", async () => {
        await page.goto("/");
        await page.getByTestId("current-user-avatar-button").click();
        await page.getByRole("menuitem", { name: "Your Profile" }).click();
      });

      await test.step("display account details", async () => {
        await expect(
          page.getByRole("heading", { name: "Chloe O'Brian", exact: true })
        ).toBeVisible();
        await expect(page.getByText("NameChloe O'Brian")).toBeVisible();
        await expect(page.getByText("Roleread-write")).toBeVisible();
      });
    });
  });

  test.describe("when logged in as read-only account", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.READ_ONLY });

    test("should access the profile page", async ({ page }) => {
      await test.step("go to profile page", async () => {
        await page.goto("/");
        await page.getByTestId("current-user-avatar-button").click();
        await page.getByRole("menuitem", { name: "Your Profile" }).click();
      });

      await test.step("display account details", async () => {
        await expect(page.getByRole("heading", { name: "Jack Bauer", exact: true })).toBeVisible();
        await expect(page.getByText("NameJack Bauer")).toBeVisible();
        await expect(page.getByText("Roleread-only")).toBeVisible();
      });
    });
  });
});
