import { expect, test } from "@playwright/test";

test.describe("Object filters", () => {
  test("should filter the objects list", async ({ page }) => {
    await test.step("access objects list and verify initial state", async () => {
      await page.goto("/objects/InfraDevice");
      await expect(page.getByRole("main")).toContainText("Filters: 0");
      await expect(page.getByRole("main")).toContainText("Showing 1 to 10 of 20 results");
    });

    await test.step("start filtering objects", async () => {
      await page.getByTestId("apply-filters").click();
      await page
        .getByTestId("side-panel-container")
        .getByText("Status")
        .locator("../..")
        .getByTestId("select-open-option-button")
        .click();
      await page.getByRole("option", { name: "Provisioning In the process" }).click();
      await page
        .getByTestId("side-panel-container")
        .getByText("Tags")
        .locator("..")
        .getByTestId("select-open-option-button")
        .click();
      await page.getByTestId("side-panel-container").getByText("red").click();
      // Closes the multiselect
      await page
        .getByTestId("side-panel-container")
        .getByText("Tags")
        .locator("..")
        .getByTestId("select-open-option-button")
        .click();
      await page.getByRole("button", { name: "Apply filters" }).scrollIntoViewIfNeeded();
      await page.getByRole("button", { name: "Apply filters" }).click();
    });

    await test.step("verify new state", async () => {
      await expect(page.getByRole("main")).toContainText("Filters: 2");
      await expect(page.getByRole("main")).toContainText("Showing 1 to 6 of 6 results");
    });

    await test.step("remove filters and verify initial state", async () => {
      await page.getByTestId("remove-filters").click();
      await expect(page.getByRole("main")).toContainText("Filters: 0");
      await expect(page.getByRole("main")).toContainText("Showing 1 to 10 of 20 results");
    });
  });
});
