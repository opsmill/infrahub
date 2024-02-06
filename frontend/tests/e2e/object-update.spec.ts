import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../constants";

test.describe("Object update", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should contain initial values and update them", async ({ page }) => {
    await page.goto("/");
    // Access all devices
    await page.getByRole("link", { name: "All Device(s)" }).click();

    // Access device details
    await page.getByRole("link", { name: "atl1-core1" }).click();

    // Open edit panel
    await page.getByRole("button", { name: "Edit" }).click();

    // Update name
    await page.getByLabel("Name *").click();
    await page.getByLabel("Name *").fill("atl1-core1-new-name");

    // Update description
    await page.getByLabel("Description").click();
    await page.getByLabel("Description").fill("New description");

    // Change status to Active
    await page
      .locator("form div")
      .filter({ hasText: "Status" })
      .nth(3)
      .getByTestId("select-open-option-button")
      .click();
    await page
      .locator("form div")
      .filter({ hasText: "Status" })
      .nth(3)
      .getByTestId("select-container")
      .getByText("Active")
      .click();

    // Update role to Edge Router
    await page
      .locator("form div")
      .filter({ hasText: "Role" })
      .nth(3)
      .getByTestId("select-open-option-button")
      .click();
    await page
      .locator("form div")
      .filter({ hasText: "Role" })
      .nth(3)
      .getByTestId("select-container")
      .getByText("Edge Router")
      .click();

    // Update ASN
    await page
      .locator("form div")
      .filter({ hasText: "Asn" })
      .nth(3)
      .getByTestId("select-open-option-button")
      .click();
    await page
      .locator("form div")
      .filter({ hasText: "Asn" })
      .nth(3)
      .getByTestId("select-container")
      .getByText("AS701")
      .click();

    // Update tags
    await page
      .getByText("Tagsblue", { exact: true })
      .getByTestId("select-open-option-button")
      .click();
    await page.getByText("Emptybluegreenred Add Tag").getByText("blue").click(); // Removes blue
    await page.getByText("Emptybluegreenred Add Tag").getByText("green").click(); // Adds green
    await page.getByText("Emptybluegreenred Add Tag").getByText("red").click(); // Adds red

    // Submit form
    await page.getByRole("button", { name: "Save" }).click();

    // Verify the alert and the closed panel
    await expect(page.getByText("Device updated")).toBeVisible();
    await expect(page.getByTestId("side-panel-background")).not.toBeVisible();

    // Verify updates in view
    await expect(
      page.locator("dd").filter({ hasText: "atl1-core1-new-name" }).locator("div")
    ).toBeVisible();
    await expect(page.getByText("New description")).toBeVisible();
    await expect(page.getByRole("link", { name: "AS701" })).toBeVisible();
    await expect(page.getByText("Active")).toBeVisible();
    await expect(page.getByText("Edge Router")).toBeVisible();
    await expect(page.getByRole("link", { name: "blue" })).not.toBeVisible();
    await expect(page.getByRole("link", { name: "green" })).toBeVisible();
    await expect(page.getByRole("link", { name: "red" })).toBeVisible();

    // Verifiy updates in form
    await page.getByRole("button", { name: "Edit" }).click();
    await expect(page.getByLabel("Name *")).toBeVisible();
    await expect(page.getByLabel("Description")).toBeVisible();
    await expect(
      page.locator("form div").filter({ hasText: "Status" }).nth(3).getByTestId("select-input")
    ).toHaveValue("Active");
    await expect(
      page.locator("form div").filter({ hasText: "Role" }).nth(3).getByTestId("select-input")
    ).toHaveValue("Edge Router");
    await expect(
      page.locator("form div").filter({ hasText: "Asn" }).nth(3).getByTestId("select-input")
    ).toHaveValue("AS701 701");
    await page.getByText("greenred").scrollIntoViewIfNeeded(); // Scroll down to display tags
    await expect(page.getByText("greenred")).toBeVisible();
  });
});
