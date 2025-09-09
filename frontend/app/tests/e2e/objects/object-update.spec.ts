import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("Object update", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("object-update");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should contain initial values and update them", async ({ page }) => {
    await test.step("access the object", async () => {
      await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);
    });

    await test.step("go to device edit form", async () => {
      await page.getByRole("link", { name: "atl1-core1" }).click();
      await page.getByTestId("edit-button").click();
    });

    await test.step("update the object", async () => {
      await page.getByLabel("Name *").fill("atl1-core1-new-name");
      await page.getByLabel("Description").fill("New description");

      await page.getByTestId("side-panel-container").getByLabel("Status").click();
      await page.getByRole("option", { name: "Maintenance" }).click();

      await page.getByTestId("side-panel-container").getByLabel("Role").click();
      await page.getByRole("option", { name: "Edge Router" }).click();

      await page.getByTestId("side-panel-container").getByLabel("Asn").click();
      await page.getByRole("option", { name: "AS174 174" }).click();

      await page.getByLabel("Tags").click();
      await page.getByText("blue").getByLabel("Remove").click(); // Removes blue
      await page.getByRole("option", { name: "green" }).click(); // Adds green
      await page.getByRole("option", { name: "red", exact: true }).click(); // Adds red
      await page.getByLabel("Tags").click(); // to close the combobox

      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("assert the updates", async () => {
      // Verify the alert and the closed panel
      await expect(page.getByText("Device updated")).toBeVisible();
      await expect(page.getByTestId("side-panel-background")).not.toBeVisible();

      // Verify updates in view
      await expect(page.getByText("Nameatl1-core1-new-name")).toBeVisible();
      await expect(page.getByTestId("object-header").getByText("New description")).toBeVisible();
      await expect(page.getByRole("link", { name: "AS174 174" })).toBeVisible();
      await expect(page.getByText("StatusMaintenance")).toBeVisible();
      await expect(page.getByText("Edge Router")).toBeVisible();
      await expect(page.getByRole("link", { name: "green" })).toBeVisible();
      await expect(page.getByRole("link", { name: "red", exact: true })).toBeVisible();
      await expect(page.getByRole("link", { name: "blue" })).not.toBeVisible();

      // Verify updates in form
      await page.getByTestId("edit-button").click();
      await expect(page.getByLabel("Name *")).toHaveValue("atl1-core1-new-name");
      await expect(page.getByLabel("Description")).toHaveValue("New description");
      await expect(page.getByLabel("Type *")).toHaveValue("MX204");
      await expect(page.getByLabel("Status")).toHaveText("Maintenance");
      await expect(page.getByLabel("Role")).toHaveText("Edge Router");
      await expect(page.getByLabel("Asn")).toHaveText("AS174 174");

      const tabInput = page.getByTestId("side-panel-container").getByText("green×red×");
      await tabInput.scrollIntoViewIfNeeded();
      await expect(tabInput).toBeVisible();
    });
  });

  test("should correctly remove values from selector", async ({ page }) => {
    await test.step("access the object", async () => {
      await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);
      await page.getByRole("link", { name: "atl1-leaf1" }).click();
    });

    await test.step("assert initial object values", async () => {
      await expect(page.getByText("Nameatl1-leaf1")).toBeVisible();
      await expect(page.getByText("RoleLeaf Switch")).toBeVisible();
      await expect(page.getByText("AsnAS64496 64496")).toBeVisible();
    });

    await test.step("edit object values", async () => {
      await page.getByTestId("edit-button").click();

      await page.getByTestId("side-panel-container").getByLabel("Status").click();
      await page.getByRole("option", { name: "Active" }).click();

      await page.getByTestId("side-panel-container").getByLabel("Role").click();
      await page.getByRole("option", { name: "Leaf Switch" }).click();

      await page.getByTestId("side-panel-container").getByLabel("Asn").click();
      await page.getByRole("option", { name: "AS64496 64496" }).click();

      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("assert new empty values", async () => {
      await expect(page.getByText("Status-")).toBeVisible();
      await expect(page.getByText("Role-")).toBeVisible();
      await expect(page.getByText("Asn-")).toBeVisible();
    });
  });
});
