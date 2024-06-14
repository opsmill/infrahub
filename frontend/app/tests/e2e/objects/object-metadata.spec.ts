import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("Object metadata", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("should contain initial values and update them", async ({ page }) => {
    await page.goto("/");

    // Access all devices
    await page.getByRole("link", { name: "All Device(s)" }).click();

    // Access device details
    await page.getByRole("link", { name: "atl1-core1" }).click();

    // Acces type metadata
    const typeRow = await page.getByText("TypeMX204");
    await typeRow.getByTestId("view-metadata-button").click();
    const metadataTooltip = await page.getByTestId("metadata-tooltip");
    await metadataTooltip.getByTestId("edit-metadata-button").click();

    // Owner should be empty
    await expect(
      page.getByTestId("select-container").nth(0).getByTestId("select-input")
    ).toHaveValue("");

    // Is visible should be checked
    await expect(page.getByLabel("is visible *")).toBeChecked();

    // Is protected should not be checked
    await expect(page.getByLabel("is protected *")).not.toBeChecked();

    // Check is protected
    await page.getByLabel("is protected *").check();

    // Select Architecture team
    await page.getByLabel("Owner").click();
    await page.getByRole("option", { name: "Account" }).click();
    await page.getByTestId("select2step-2").getByTestId("select-open-option-button").nth(0).click();
    await page.getByRole("option", { name: "Architecture Team" }).click();

    // Save
    await page.getByRole("button", { name: "Save" }).click();

    // Verify the alert
    await expect(page.getByText("Metadata updated")).toBeVisible();

    // Verify metadata updates
    await page.goto("/");

    // Access all devices
    await page.getByRole("link", { name: "All Device(s)" }).click();

    // Access device details
    await page.getByRole("link", { name: "atl1-core1" }).click();

    // Acces type metadata
    const typeRowUpdated = await page.getByText("TypeMX204");
    await typeRowUpdated.getByTestId("view-metadata-button").click();
    const metadataTooltipUpdated = await page.getByTestId("metadata-tooltip");
    await metadataTooltipUpdated.getByTestId("edit-metadata-button").click();

    // Source should be Account + Pop-Builder
    await expect(
      page.getByTestId("select-container").nth(0).getByTestId("select-input")
    ).toHaveValue("Account");
    await expect(
      page.getByTestId("select-container").nth(1).getByTestId("select-input")
    ).toHaveValue("Architecture Team");

    // Is protected should be checked
    await expect(page.getByLabel("is protected *")).toBeChecked();
  });
});
