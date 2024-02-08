import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../../../constants";

test.describe("Object update", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should contain initial values and update them", async ({ page }) => {
    await test.step("access the object", async () => {
      await page.goto("/objects/InfraDevice");
    });

    await test.step("go to device edit form", async () => {
      await page.getByRole("link", { name: "atl1-core1" }).click();
      await page.getByRole("button", { name: "Edit" }).click();
    });

    await test.step("update the object", async () => {
      await page.getByLabel("Name *").fill("atl1-core1-new-name");
      await page.getByLabel("Description").fill("New description");

      await page
        .getByTestId("side-panel-container")
        .getByText("Status")
        .locator("../..")
        .getByTestId("select-open-option-button")
        .click();
      await page.getByRole("option", { name: "Active" }).click();

      await page
        .getByTestId("side-panel-container")
        .getByText("Role")
        .locator("../..")
        .getByTestId("select-open-option-button")
        .click();
      await page.getByRole("option", { name: "Edge Router" }).click();

      await page
        .getByTestId("side-panel-container")
        .getByText("Asn")
        .locator("../..")
        .getByTestId("select-open-option-button")
        .click();
      await page.getByRole("option", { name: "AS701" }).click();

      await page
        .getByTestId("side-panel-container")
        .getByText("Tags")
        .locator("..")
        .getByTestId("select-open-option-button")
        .click();
      await page.getByRole("option", { name: "blue" }).click(); // Removes blue
      await page.getByRole("option", { name: "green" }).click(); // Adds green
      await page.getByRole("option", { name: "red" }).click(); // Adds red

      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("assert the updates", async () => {
      // Verify the alert and the closed panel
      await expect(page.getByText("Device updated")).toBeVisible();
      await expect(page.getByTestId("side-panel-background")).not.toBeVisible();

      // Verify updates in view
      await expect(page.getByText("Nameatl1-core1-new-name")).toBeVisible();
      await expect(page.getByText("New description")).toBeVisible();
      await expect(page.getByRole("link", { name: "AS701" })).toBeVisible();
      await expect(page.getByText("Active")).toBeVisible();
      await expect(page.getByText("Edge Router")).toBeVisible();
      await expect(page.getByRole("link", { name: "green" })).toBeVisible();
      await expect(page.getByRole("link", { name: "red" })).toBeVisible();
      await expect(page.getByRole("link", { name: "blue" })).not.toBeVisible();

      // Verify updates in form
      await page.getByRole("button", { name: "Edit" }).click();
      await expect(page.getByLabel("Name *")).toHaveValue("atl1-core1-new-name");
      await expect(page.getByLabel("Description")).toHaveValue("New description");
      await expect(page.getByLabel("Type *")).toHaveValue("MX204");
      await expect(
        page
          .getByTestId("side-panel-container")
          .getByText("Status")
          .locator("../..")
          .getByTestId("select-input")
      ).toHaveValue("Active");
      await expect(
        page
          .getByTestId("side-panel-container")
          .getByText("Role")
          .locator("../..")
          .getByTestId("select-input")
      ).toHaveValue("Edge Router");
      await expect(
        page
          .getByTestId("side-panel-container")
          .getByText("Asn")
          .locator("../..")
          .getByTestId("select-input")
      ).toHaveValue("AS701 701");

      const tabInput = page.getByTestId("side-panel-container").getByText("greenred");
      await tabInput.scrollIntoViewIfNeeded();
      await expect(tabInput).toBeVisible();
    });
  });
});
