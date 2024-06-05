import { expect, test } from "@playwright/test";

test.describe("Object filters", () => {
  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("should filter the objects list", async ({ page }) => {
    await test.step("access objects list and verify initial state", async () => {
      await page.goto("/objects/InfraDevice");
      await expect(page.getByRole("main")).toContainText("Filters: 0");
      await expect(page.getByRole("main")).toContainText("Showing 1 to 10 of 30 results");
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

      const tagsMultiSelectOpenButton = page
        .getByTestId("side-panel-container")
        .getByText("Tags")
        .locator("../..")
        .getByTestId("select-open-option-button");
      await tagsMultiSelectOpenButton.click();

      await page.getByTestId("side-panel-container").getByText("red").click();

      // Closes the multiselect
      await tagsMultiSelectOpenButton.click();

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
      await expect(page.getByRole("main")).toContainText("Showing 1 to 10 of 30 results");
    });
  });

  test("should correctly display the filters with select 2 steps pointing to any objects", async ({
    page,
  }) => {
    await page.goto("/objects/CoreArtifact");
    await page.getByTestId("apply-filters").click();
    await expect(page.getByTestId("side-panel-container").getByText("Object")).toBeVisible();
    await page.getByTestId("select2step-1").getByTestId("select-open-option-button").click();
    await expect(page.getByRole("option", { name: "Tag", exact: true })).toBeVisible();
  });
});
