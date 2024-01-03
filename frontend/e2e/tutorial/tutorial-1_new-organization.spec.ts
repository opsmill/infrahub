import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../tests/utils";

test.describe("Getting started with Infrahub", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("1. Create a new organization", async ({ page }) => {
    await page.goto("/");

    await page.getByTestId("sidebar-menu").getByRole("link", { name: "Organization" }).click();
    await page.getByTestId("create-object-button").click();

    // Form
    await page.getByLabel("Name *").fill("my-first-org");
    await page.getByLabel("Description").fill("Testing Infrahub");
    await page.getByRole("button", { name: "Create" }).click();

    // Then
    await expect(page.locator("#alert-success")).toContainText("Organization created");
    await expect(page.locator("tbody")).toContainText("my-first-org");
    await expect(page.locator("tbody")).toContainText("My-First-Org");
    await expect(page.locator("tbody")).toContainText("Testing Infrahub");
  });
});
