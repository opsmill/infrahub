import { test, expect } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/objects/CoreGenericAccount - Admin permissions", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should be allowed to add accounts", async ({ page }) => {
    await page.goto("/objects/CoreGenericAccount");
    await expect(page.getByTestId("create-object-button")).toBeEnabled();
  });
});

test.describe("/objects/CoreGenericAccount - Read write permissions", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.READ_WRITE });
  test("should not be allowed to add accounts", async ({ page }) => {
    await page.goto("/objects/CoreGenericAccount");
    await expect(page.getByTestId("create-object-button")).not.toBeEnabled();
  });
});

test.describe("/objects/CoreGenericAccount - Read only permissions", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.READ_ONLY });
  test("should not be allowed to add accounts", async ({ page }) => {
    await page.goto("/objects/CoreGenericAccount");
    await expect(page.getByTestId("create-object-button")).not.toBeEnabled();
  });
});
