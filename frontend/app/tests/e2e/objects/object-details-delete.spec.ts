import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

const BRANCH_NAME = "object-details-delete";

test.describe("Object details - delete", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("delete an object and redirects to list view", async ({ page }) => {
    await page.goto(`/objects/BuiltinTag?branch=${BRANCH_NAME}`);
    await expect(page.getByTestId("branch-selector-trigger")).toContainText(
      "object-details-delete"
    );

    await test.step("go to blue tag details", async () => {
      await page.getByRole("link", { name: "blue" }).click();
    });

    await test.step("delete blue tag", async () => {
      await page.getByTestId("object-details-menu").click();
      await page.getByRole("menuitem", { name: "Delete" }).click();
      await expect(page.getByTestId("modal-delete")).toContainText(
        'Are you sure you want to remove the Tag"blue"?'
      );
      await page.getByTestId("modal-delete-confirm").click();
      await expect(page.getByText("Object blue deleted")).toBeVisible();
      await expect(page.getByRole("link", { name: "blue" })).toBeHidden();
    });

    await test.step("user is still on the same branch after delete", async () => {
      await expect(page.getByTestId("branch-selector-trigger")).toContainText(
        "object-details-delete"
      );
    });
  });
});
