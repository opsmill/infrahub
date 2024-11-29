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
      // eslint-disable-next-line quotes
      await page.goto('/objects/InfraInterfaceL2?pagination={"limit":10, "offset": 20}');
      await page.getByRole("cell", { name: "Ethernet11" }).first().click();
    });

    await page.getByTestId("edit-button").click();

    await test.step("Select multiple tags", async () => {
      await page.getByLabel("Tags").click();
      await page.getByRole("option", { name: "blue" }).click();
      await expect(page.getByRole("option", { name: "blue" })).not.toBeVisible();
      await page.getByRole("option", { name: "green" }).click();
      await expect(page.getByRole("option", { name: "green" })).not.toBeVisible();
      await page.getByRole("option", { name: "red" }).click();
      await expect(page.getByRole("option", { name: "red" })).not.toBeVisible();
      await expect(page.locator("form")).toContainText("blue×green×red×");
    });

    await test.step("Remove a tag when clicking on selected badge", async () => {
      await page.getByText("red×").getByLabel("Remove").click();
      await expect(page.locator("form")).toContainText("blue×green×");
    });

    await test.step("Create a new tag directly on multi select", async () => {
      await page.getByRole("button", { name: "+ Add new Tag" }).click();
      await page.getByTestId("new-object-form").getByLabel("Name *").fill("new tag");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("blue×green×new tag×")).toBeVisible();
    });
  });
});
