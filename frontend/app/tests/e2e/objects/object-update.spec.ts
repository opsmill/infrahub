import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("Object update", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("should contain initial values and update them", async ({ page }) => {
    await test.step("access the object", async () => {
      await page.goto("/objects/InfraDevice");
    });

    await test.step("go to device edit form", async () => {
      await page.getByRole("link", { name: "atl1-core1" }).click();
      await page.getByTestId("edit-button").click();
    });

    await test.step("update the object", async () => {
      await page.getByLabel("Name *").fill("atl1-core1-new-name");
      await page.getByLabel("Description").fill("New description");

      await page.getByTestId("side-panel-container").getByLabel("Status").click();
      await page.getByRole("option", { name: "Active" }).click();

      await page.getByTestId("side-panel-container").getByLabel("Role").click();
      await page.getByRole("option", { name: "Edge Router" }).click();

      await page.getByTestId("side-panel-container").getByLabel("Asn").click();
      await page.getByRole("option", { name: "AS701 701" }).click();

      const tagsMultiSelectOpenButton = page.getByTestId("side-panel-container").getByLabel("Tags");
      await tagsMultiSelectOpenButton.click();

      await page.getByRole("option", { name: "blue" }).click(); // Removes blue
      await page.getByRole("option", { name: "green" }).click(); // Adds green
      await page.getByRole("option", { name: "red", exact: true }).click(); // Adds red

      await page.getByTestId("side-panel-container").getByLabel("Tags").click();

      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("assert the updates", async () => {
      // Verify the alert and the closed panel
      await expect(page.getByText("Device updated")).toBeVisible();
      await expect(page.getByTestId("side-panel-background")).not.toBeVisible();

      // Verify updates in view
      await expect(page.getByText("Nameatl1-core1-new-name")).toBeVisible();
      await expect(page.getByText("New description")).toBeVisible();
      await expect(page.getByRole("link", { name: "AS701 701" })).toBeVisible();
      await expect(page.getByText("Active")).toBeVisible();
      await expect(page.getByText("Edge Router")).toBeVisible();
      await expect(page.getByRole("link", { name: "green" })).toBeVisible();
      await expect(page.getByRole("link", { name: "red", exact: true })).toBeVisible();
      await expect(page.getByRole("link", { name: "blue" })).not.toBeVisible();

      // Verify updates in form
      await page.getByTestId("edit-button").click();
      await expect(page.getByLabel("Name *")).toHaveValue("atl1-core1-new-name");
      await expect(page.getByLabel("Description")).toHaveValue("New description");
      await expect(page.getByLabel("Type *")).toHaveValue("MX204");
      await expect(page.getByLabel("Status")).toHaveText("Active");
      await expect(page.getByLabel("Role")).toHaveText("Edge Router");
      await expect(page.getByLabel("Asn")).toHaveText("AS701 701");

      const tabInput = page.getByTestId("side-panel-container").getByText("greenred");
      await tabInput.scrollIntoViewIfNeeded();
      await expect(tabInput).toBeVisible();
    });
  });

  test("should correctly remove values from selector", async ({ page }) => {
    await test.step("access the object", async () => {
      await page.goto("/objects/InfraDevice/");
      await page.getByRole("link", { name: "atl1-leaf1" }).click();
    });

    await test.step("assert initial object values", async () => {
      await expect(page.getByText("Nameatl1-leaf1")).toBeVisible();
      await expect(page.getByText("StatusActive")).toBeVisible();
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
