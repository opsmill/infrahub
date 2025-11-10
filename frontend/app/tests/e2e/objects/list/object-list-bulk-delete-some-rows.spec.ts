import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../../constants";
import { generateRandomBranchName } from "../../../utils";
import { createBranchAPI, deleteBranchAPI } from "../../utils/graphql";

test.describe("/objects/BuiltinTag - Bulk delete some rows", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("bulk-delete-some-rows");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should be able to delete objects", async ({ page }) => {
    await test.step("assert we have the initial values", async () => {
      await page.goto(`/objects/BuiltinTag?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("button", { name: "Add Tag" })).toBeVisible();
      await expect(
        page
          .locator("a")
          .filter({ hasText: "blue" })
          .locator("..")
          .getByTestId("identifier-checkbox-cell")
      ).toBeVisible();
      await expect(
        page
          .locator("a")
          .filter({ hasText: "green" })
          .locator("..")
          .getByTestId("identifier-checkbox-cell")
      ).toBeVisible();
    });

    await test.step("proceed delete", async () => {
      await page
        .locator("a")
        .filter({ hasText: "blue" })
        .locator("..")
        .getByTestId("identifier-checkbox-cell")
        .click();

      await page
        .locator("a")
        .filter({ hasText: "green" })
        .locator("..")
        .getByTestId("identifier-checkbox-cell")
        .click();

      await page
        .getByTestId("object-table-toolbar")
        .getByRole("button", { name: "Delete" })
        .click();
      await expect(page.getByText("Are you sure you want to")).toBeVisible();
      await page.getByTestId("modal-delete-confirm").click();
      await expect(page.getByText("Objects deleted!")).toBeVisible();
    });

    await test.step("assert the objects were deleted", async () => {
      await expect(page.getByRole("link", { name: "red" })).toBeVisible();
      await expect(page.getByRole("link", { name: "blue" })).not.toBeVisible();
      await expect(page.getByRole("link", { name: "green" })).not.toBeVisible();
    });
  });
});
