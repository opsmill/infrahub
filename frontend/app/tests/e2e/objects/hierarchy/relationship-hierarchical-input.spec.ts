import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../../constants";
import { generateRandomBranchName } from "../../../utils";
import { createBranchAPI, deleteBranchAPI } from "../../utils/graphql";

test.describe("Relationship hierarchical input", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("relationship-hierarchical-input");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should select a site using the Explore tab of relationship input", async ({ page }) => {
    await test.step("navigate to InfraDevice creation page", async () => {
      await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);
      await page.getByTestId("create-object-button").click();
      await page.getByRole("button", { name: "Start from scratch" }).click();
    });

    await test.step("open site selection and verify All tab", async () => {
      await page.getByLabel("Site").click();
      await expect(page.getByRole("tab", { name: "All" })).toBeVisible();
      await expect(page.getByRole("option", { name: "atl1" })).toBeVisible();
    });

    await test.step("navigate through hierarchy in Explore tab", async () => {
      await page.getByRole("tab", { name: "Explore" }).click();
      await page.getByRole("option", { name: "North America Continent" }).click();
      await page.getByRole("option", { name: "United States of America" }).click();
      await page.getByRole("option", { name: "atl1 Site" }).click();
    });

    await test.step("verify selected site", async () => {
      await expect(page.getByLabel("Site")).toContainText("atl1");
    });
  });
});
