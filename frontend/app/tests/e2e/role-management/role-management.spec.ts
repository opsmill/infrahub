import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

const BRANCH_NAME = "role-management";

test.describe("Users & Permissions - Read-Only User", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.READ_ONLY });

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("Should not be allowed to read page", async ({ page }) => {
    await page.goto(`/role-management?branch=${BRANCH_NAME}`);
    await expect(page.locator("#root")).toContainText("You can't access this view");
  });
});

test.describe("Users & Permissions - Admin User", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should be allowed to add accounts", async ({ page }) => {
    await page.goto(`/role-management?branch=${BRANCH_NAME}`);
    await expect(page.getByTestId("create-object-button")).toBeEnabled();
  });
});
