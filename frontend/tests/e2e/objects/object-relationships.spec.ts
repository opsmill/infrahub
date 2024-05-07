import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/objects/:objectname/:objectid - relationship tab", () => {
  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test.describe("when not logged in", () => {
    test("should not be able to edit relationship", async ({ page }) => {
      await test.step("Navigate to relationship tab of an object", async () => {
        await page.goto("/objects/InfraPlatform");
        await page.getByRole("link", { name: "Juniper JunOS" }).click();
        await page.getByText(/Devices9|Devices10/).click(); // since this test can run in parallel with the "should delete the relationship" test
      });

      await test.step("all buttons are disabled", async () => {
        await expect(page.getByRole("button", { name: "Edit" })).toBeDisabled();
        await expect(page.getByRole("button", { name: "Manage groups" })).toBeDisabled();
        await expect(page.getByTestId("open-relationship-form-button")).toBeDisabled();
      });
    });
  });

  test.describe("when logged in as Admin", () => {
    test.describe.configure({ mode: "serial" });
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should delete the relationship", async ({ page }) => {
      await test.step("Navigate to relationship tab of an object", async () => {
        await page.goto("/objects/InfraPlatform");
        await page.getByRole("link", { name: "Juniper JunOS" }).click();
        await page.getByText("Devices10").click();
      });

      await test.step("Delete the relationship", async () => {
        await page
          .getByRole("row", { name: "dfw1-core1" })
          .getByTestId("relationship-delete-button")
          .click();
        await expect(page.getByRole("paragraph")).toContainText(
          "Are you sure you want to remove the association between `Juniper JunOS` and `dfw1-core1`? The `InfraDevice` `dfw1-core1` won't be deleted in the process."
        );
        await page.getByTestId("modal-delete-confirm").click();
      });

      await test.step("Verify deletion of relationship", async () => {
        await expect(page.getByRole("alert")).toContainText("Item removed from the group");
        await expect(page.getByRole("main")).toContainText("Showing 1 to 9 of 9 results");
        await expect(page.getByLabel("Tabs")).toContainText("Devices9");
      });
    });

    test("should be add a new relationship", async ({ page }) => {
      await test.step("Navigate to relationship tab of an object", async () => {
        await page.goto("/objects/InfraPlatform");
        await page.getByRole("link", { name: "Juniper JunOS" }).click();
        await page.getByText("Devices9").click();
      });

      await test.step("Add a new relationship", async () => {
        await page.getByTestId("open-relationship-form-button").click();
        await page.getByTestId("select2step-1").getByTestId("select-open-option-button").click();
        await page.getByRole("option", { name: "Device" }).click();
        await page.getByTestId("select2step-2").getByTestId("select-open-option-button").click();
        await page.getByRole("option", { name: "dfw1-core1" }).click();
        await page.getByRole("button", { name: "Save" }).click();
      });

      await test.step("Verify new relationship addition", async () => {
        await expect(page.getByRole("alert")).toContainText("Association with InfraDevice added");
        await expect(page.getByRole("main")).toContainText("Showing 1 to 10 of 10 results");
        await expect(page.getByLabel("Tabs")).toContainText("Devices10");
        await expect(page.getByRole("cell", { name: "dfw1-core1" })).toBeVisible();
      });
    });
  });
});
