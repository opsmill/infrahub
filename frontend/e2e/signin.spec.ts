import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH, ADMIN_CREDENTIALS } from "../tests/utils";

test.describe("/signin", () => {
  test("should log in the user", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("link", { name: "Sign in" }).click();
    await expect(page.getByText("Sign in to your account")).toBeVisible();
    await page.getByLabel("Username").fill(ADMIN_CREDENTIALS.username);
    await page.getByLabel("Password").fill(ADMIN_CREDENTIALS.password);
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page.getByTestId("current-user-avatar-button")).toBeVisible();
  });

  test.describe("When logged in", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should log out the user", async ({ page }) => {
      await page.goto("/");

      await page.getByTestId("current-user-avatar-button").click();
      await page.getByRole("menuitem", { name: "Sign out" }).click();

      await expect(page.getByRole("link", { name: "Sign in" })).toBeVisible();
    });
  });
});
