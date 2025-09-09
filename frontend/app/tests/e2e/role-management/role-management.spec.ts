import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("Users & Permissions - Read-Only User", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.READ_ONLY });

  test("Should not be allowed to read page", async ({ page }) => {
    await page.goto("/role-management");
    await page.getByRole("link", { name: "Roles" }).click();
    await expect(page.locator("#root")).toContainText("You can't access this view");
  });
});

test.describe("Users & Permissions - Admin User", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should be allowed to add accounts", async ({ page }) => {
    await page.goto("/role-management");
    await expect(page.getByTestId("create-object-button")).toBeEnabled();
  });
});
