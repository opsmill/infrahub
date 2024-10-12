import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("Role Management - Admin", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should be allowed to add accounts", async ({ page }) => {
    await page.goto("/role-management");
    await expect(page.getByTestId("create-object-button")).toBeEnabled();
  });
});
