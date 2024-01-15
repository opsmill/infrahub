import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../../../utils";

test.describe("/objects/:objectname/:objectid", () => {
  test.describe("when not logged in", () => {
    test("should not be able to edit object", async ({ page }) => {
      await page.goto("/objects/InfraBGPSession");
      await page.getByRole("cell", { name: "EXTERNAL" }).first().click();

      await expect(page.getByRole("button", { name: "Edit" })).toBeDisabled();
      await expect(page.getByRole("button", { name: "Manage groups" })).toBeDisabled();
    });
  });

  test.describe("when logged in as Admin", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should be able to edit object", async ({ page }) => {
      await page.goto("/objects/InfraBGPSession");
      await page.getByRole("link", { name: "EXTERNAL" }).first().click();

      await expect(page.getByRole("button", { name: "Edit" })).toBeEnabled();
      await expect(page.getByRole("button", { name: "Manage groups" })).toBeEnabled();
    });

    test("should display relationships correctly", async ({ page }) => {
      await page.goto("/objects/InfraBGPSession");
      await page.getByRole("cell", { name: "EXTERNAL" }).first().click();

      // Attribute
      await expect(page.locator("dl")).toContainText("ID");
      await expect(page.locator("dl")).toContainText("Type");
      await expect(page.locator("dl")).toContainText("Description");
      await expect(page.locator("dl")).toContainText("Import Policies");
      await expect(page.locator("dl")).toContainText("Export Policies");
      await expect(page.locator("dl")).toContainText("Status");
      await expect(page.locator("dl")).toContainText("Role");

      // Relationships Attributes
      await expect(page.locator("dl")).toContainText("Local As");
      await expect(page.locator("dl")).toContainText("Remote As");
      await expect(page.locator("dl")).toContainText("Local Ip");
      await expect(page.locator("dl")).toContainText("Remote Ip");
      await expect(page.locator("dl")).toContainText("Peer Group");
      await expect(page.locator("dl")).toContainText("Peer Session");

      // Relationships Generics
      await expect(page.locator("dl")).toContainText("Device");
    });
  });
});
