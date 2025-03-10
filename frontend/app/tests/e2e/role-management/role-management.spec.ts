import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

const BRANCH_NAME_READ_ONLY = "role-management-read-only";

test.describe("Users & Permissions - Read-Only User", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.READ_ONLY });

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME_READ_ONLY);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME_READ_ONLY);
  });

  test("Should not be allowed to read page", async ({ page }) => {
    await page.goto(`/role-management?branch=${BRANCH_NAME_READ_ONLY}`);
    await expect(page.locator("#root")).toContainText("You can't access this view");
  });
});

const BRANCH_NAME_ADMIN = "role-management-admin";

test.describe("Users & Permissions - Admin User", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME_ADMIN);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME_ADMIN);
  });

  test("should be allowed to add accounts", async ({ page }) => {
    await page.goto(`/role-management?branch=${BRANCH_NAME_ADMIN}`);
    await expect(page.getByTestId("create-object-button")).toBeEnabled();
  });
});
