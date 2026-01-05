import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("object dropdown creation", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  const BRANCH_NAME = generateRandomBranchName();

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should open the creation form and open the tag option creation form", async ({ page }) => {
    await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);

    // Open creation form
    await page.getByTestId("create-object-button").click();
    await page.getByRole("button", { name: "Start from scratch" }).click();

    // Open tags options
    await page.getByLabel("Tags").click();

    // Add new option
    await page.getByRole("button", { name: "+ Add new Tag" }).click();

    // Assert form content is visible
    await expect(page.getByText("Create Tag")).toBeVisible();
    await expect(page.getByRole("button", { name: "Save" })).toBeVisible();

    // Create a new tag
    await page.getByTestId("new-object-form").getByLabel("Name").fill("new-tag");
    await page.getByTestId("new-object-form").getByLabel("Description").fill("New tag description");

    // Submit
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.getByText("Tag created")).toBeVisible();

    // Closes the form
    await page.getByRole("button", { name: "Cancel" }).click();
  });

  test("should not be able to create a new option for dropdown", async ({ page }) => {
    await page.goto(`/objects/CoreWebhook?branch=${BRANCH_NAME}`);
    await page.getByTestId("create-object-button").click();
    await page.getByRole("combobox", { name: "Select an object type" }).click();
    await page.getByRole("option", { name: "Custom Webhook Core" }).click();
    await page.getByRole("combobox", { name: "Branch Scope" }).click();
    expect(await page.getByTestId("add-option-button")).toBeHidden();
  });
});
