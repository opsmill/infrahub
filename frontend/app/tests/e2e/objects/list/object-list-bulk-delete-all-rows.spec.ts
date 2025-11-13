import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../../constants";
import { generateRandomBranchName } from "../../../utils";
import { createBranchAPI, deleteBranchAPI } from "../../utils/graphql";

test.describe("/objects/BuiltinTag - Bulk delete all rows", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("bulk-delete-all-rows");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("delete all rows", async ({ page }) => {
    await test.step("assert we have the initial values", async () => {
      await page.goto(`/objects/BuiltinTag?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("link", { name: "green" })).toBeVisible();
      await expect(page.getByTestId("identifier-checkbox-cell")).toHaveCount(3);
    });

    await test.step("select all rows", async () => {
      await page.getByTestId("select-all-rows").click();
      await expect(page.getByTestId("identifier-checkbox-cell").nth(0)).toBeChecked();
      await expect(page.getByTestId("identifier-checkbox-cell").nth(1)).toBeChecked();
      await expect(page.getByTestId("identifier-checkbox-cell").nth(2)).toBeChecked();
    });

    await test.step("delete all rows", async () => {
      await page
        .getByTestId("object-table-toolbar")
        .getByRole("button", { name: "Delete" })
        .click();
      await expect(page.getByText("Are you sure you want to")).toBeVisible();
      await page.getByTestId("modal-delete-confirm").click();
      await expect(page.getByText("Objects deleted!")).toBeVisible();
      await expect(page.getByText("No Tag found")).toBeVisible();
    });
  });
});
