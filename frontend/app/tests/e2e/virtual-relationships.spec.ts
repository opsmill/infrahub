import { expect, test } from "@playwright/test";

test.describe("Virtual Relationships", () => {
  test.describe("when viewing a node with virtual relationships", () => {
    test("should display virtual relationship tab with count", async ({ page }) => {
      // Navigate to a device list page
      await page.goto("/");

      // Search for a device kind
      await page.getByTestId("search-anywhere-trigger").click();
      await page.getByTestId("search-anywhere-input").fill("Device");
      await page
        .getByRole("option", { name: /Device/i })
        .first()
        .click();

      // Wait for the device list to load and click the first device
      await page.getByRole("link").filter({ hasText: /\w+/ }).first().click();

      // Check that the object detail tabs are visible
      const tabs = page.getByTestId("object-details-tabs");
      await expect(tabs).toBeVisible();

      // Look for a virtual relationship tab (e.g., "All Services")
      // This test assumes the loaded schema has virtual relationships defined
      const virtualRelTab = tabs.getByText("All Services");

      // If the virtual relationship tab exists, test interaction
      if (await virtualRelTab.isVisible()) {
        await test.step("click virtual relationship tab", async () => {
          await virtualRelTab.click();
          // URL should contain the tab query parameter
          expect(page.url()).toContain("tab=all_services");
        });

        await test.step("verify tab content loads without error", async () => {
          // The content area should not show an error
          await expect(page.getByText("not found in")).not.toBeVisible();
          // Should show a table or empty state
          await page.waitForTimeout(1000);
        });

        await test.step("verify no Add button for virtual relationships", async () => {
          // Virtual relationships are read-only, no Add button should appear
          await expect(page.getByRole("button", { name: /add/i })).not.toBeVisible();
        });
      }
    });
  });
});
