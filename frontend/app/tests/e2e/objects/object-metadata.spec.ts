import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("Object metadata", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should contain initial values and update them", async ({ page }) => {
    await page.goto("/objects/InfraDevice");

    // Access device details
    await page.getByRole("link", { name: "atl1-core2" }).click();

    // Acces type metadata
    const typeRow = await page.getByText("TypeMX204");
    await typeRow.getByTestId("view-metadata-button").click();
    const metadataTooltip = await page.getByTestId("metadata-tooltip");
    await metadataTooltip.getByTestId("edit-metadata-button").click();

    // Owner should be empty
    await expect(page.getByLabel("Kind").first().getByTestId("select-value")).not.toBeVisible();

    // Is visible should be checked
    await expect(page.getByLabel("is visible *")).toBeChecked();

    // Is protected should not be checked
    await expect(page.getByLabel("is protected *")).not.toBeChecked();

    // Check is protected
    await page.getByLabel("is protected *").check();

    // Select Architecture team
    await page.getByLabel("Kind").first().click();
    await page.getByRole("option", { name: "Account group" }).click();
    await page.getByLabel("Account group").click();
    await page.getByRole("option", { name: "Architecture Team" }).click();

    // Save
    await page.getByRole("button", { name: "Save" }).click();

    // Verify the alert
    await expect(page.getByText("Metadata updated")).toBeVisible();

    // Access all devices
    await page.goto("/objects/InfraDevice");

    // Access device details
    await page.getByRole("link", { name: "atl1-core2" }).click();

    // Acces type metadata
    const typeRowUpdated = await page.getByText("TypeMX204");
    await typeRowUpdated.getByTestId("view-metadata-button").click();
    const metadataTooltipUpdated = await page.getByTestId("metadata-tooltip");
    await metadataTooltipUpdated.getByTestId("edit-metadata-button").click();

    // Source should be Account + Pop-Builder
    await expect(page.getByTestId("select-value").nth(0)).toContainText("Account group");
    await expect(page.getByTestId("select-value").nth(1)).toContainText("Architecture Team");

    // Is protected should be checked
    await expect(page.getByLabel("is protected *")).toBeChecked();
  });

  test("read only attribute should not have metadata edit button", async ({ page }) => {
    await page.goto("/objects/InfraDevice");
    await page.getByRole("link", { name: "atl1-core2" }).click();

    const descriptionRow = await page.getByText("Computed DescriptionMX204");
    await descriptionRow.getByTestId("view-metadata-button").click();
    await expect(page.getByRole("cell", { name: "Source" })).toBeVisible();
    await expect(page.getByTestId("edit-metadata-button")).not.toBeVisible();
  });
});
