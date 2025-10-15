import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../../constants";
import { generateRandomBranchName } from "../../../utils";
import { createBranchAPI, deleteBranchAPI } from "../../utils/graphql";

test.describe("/objects/:objectKind - Bulk edit some rows", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  const BRANCH_NAME = generateRandomBranchName("bulk-edit-some-rows");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should be able to update multiple objects at once", async ({ page }) => {
    await test.step("navigate to objects page and select items", async () => {
      await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);
      await page.getByTestId("identifier-checkbox-cell").nth(0).click();
      await page.getByTestId("identifier-checkbox-cell").nth(1).click();
      await page.getByTestId("identifier-checkbox-cell").nth(2).click();
      await page.getByTestId("object-table-toolbar").getByRole("button", { name: "Edit" }).click();
    });

    await test.step("verify bulk edit panel is displayed correctly", async () => {
      await expect(
        page.getByRole("heading", { name: "objects selected for editing" })
      ).toBeVisible();
      await expect(page.getByText("atl1-core1Waiting for changes")).toBeVisible();
      await expect(page.getByText("atl1-core2Waiting for changes")).toBeVisible();
      await expect(page.getByText("atl1-edge1Waiting for changes")).toBeVisible();
      await expect(page.getByRole("heading", { name: "Set bulk changes" })).toBeVisible();
      await expect(page.getByLabel("Description")).toBeVisible();
      await expect(page.getByLabel("Name")).toBeHidden();
      await expect(page.getByLabel("Member of groups")).toBeHidden();
      await expect(page.getByLabel("Edit").getByText("Description")).toBeVisible();
    });

    await test.step("make bulk changes", async () => {
      await page.getByLabel("Site").click();
      await page.getByRole("option", { name: "den1" }).click();
      await page.getByLabel("Description").fill("test desc");
      await page.getByLabel("Type").fill("test type");
      await page.getByLabel("Status").click();
      await page.getByRole("option", { name: "Drained Temporarily taken out" }).click();
      await page.getByLabel("Role").click();
      await page.getByRole("option", { name: "Leaf Switch Top of Rack part" }).click();
      await page.getByTestId("select-open-pool-option-button").click();
      await page.getByRole("option", { name: "Loopbacks pool" }).click();
      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("verify changes were applied successfully", async () => {
      await expect(page.getByText("atl1-core1success")).toBeVisible();
      await expect(page.getByText("atl1-core2success")).toBeVisible();
      await expect(page.getByText("atl1-edge1success")).toBeVisible();
      await expect(page.getByText("Drained").nth(0)).toBeVisible();
      await expect(page.getByText("Drained").nth(1)).toBeVisible();
      await expect(page.getByText("Drained").nth(2)).toBeVisible();
    });
  });
});
