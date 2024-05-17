import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("Verify multi select behaviour", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("select, remove and create tags using multi-select", async ({ page }) => {
    await test.step("Navigate to Ethernet11", async () => {
      await page.goto("/objects/InfraInterfaceL2?pagination={\"limit\":10, \"offset\": 20}");
      await page.getByRole("cell", { name: "Ethernet11" }).first().click();
    });

    await page.getByRole("button", { name: "Edit" }).click();

    await test.step("Select multiple tags", async () => {
      const tagsMultiSelectOpenButton = page
        .getByTestId("side-panel-container")
        .getByText("Tags")
        .locator("..")
        .getByTestId("select-open-option-button");
      await tagsMultiSelectOpenButton.click();
      await page.getByRole("option", { name: "blue" }).click();
      await page.getByRole("option", { name: "green" }).click();
      await page.getByRole("option", { name: "red" }).click();
      await expect(page.locator("form")).toContainText("bluegreenred");
    });

    await test.step("Remove a tag when clicking on selected input", async () => {
      await page.getByRole("option", { name: "red" }).click();
      await expect(page.getByRole("option", { name: "Add Tag" })).toBeVisible();
      await expect(page.locator("form")).toContainText("bluegreen");
    });

    await test.step("Remove a tag when clicking on selected badge", async () => {
      await page
        .getByTestId("multi-select-input-badge")
        .filter({ hasText: "green" })
        .getByTestId("badge-delete")
        .click();
      await expect(page.locator("form")).toContainText("blue");
    });

    await test.step("Create a new tag directly on multi select", async () => {
      await page.getByRole("option", { name: "Add Tag" }).click();
      await page.getByLabel("Create Tag").locator("#Name").fill("new tag");
      await page.getByRole("button", { name: "Create" }).click();
      await expect(page.locator("form").first()).toContainText("bluenew tag");
    });
  });
});
