import { expect, test } from "@playwright/test";

test.describe("/schema - Schema visualizer", () => {
  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("display help menu correctly", async ({ page }) => {
    await page.goto("/schema");

    await test.step("open schema viewer", async () => {
      await page.getByText("CoreArtifact", { exact: true }).click();
      await expect(page.getByTestId("schema-viewer")).toBeVisible();
    });

    await test.step("open help menu", async () => {
      await page.getByTestId("schema-help-menu-trigger").click();
      await expect(page.getByTestId("schema-help-menu-content")).toBeVisible();
    });

    await test.step("help menu with documentation and list view link", async () => {
      await expect(page.getByRole("menuitem", { name: "Documentation" })).toBeEnabled();
      await expect(page.getByRole("menuitem", { name: "Open list view" })).toBeEnabled();
    });

    await test.step("close menu when presss Esc", async () => {
      await page.locator("body").press("Escape");
      await expect(page.getByTestId("schema-help-menu-content")).not.toBeVisible();
    });

    await test.step("help menu for a schema without documentation not list view link", async () => {
      await page.getByText("CoreThread - Artifact").click();
      await page.getByTestId("schema-help-menu-trigger").click();
      await expect(page.getByRole("menuitem", { name: "Documentation" })).toBeDisabled();
      await expect(page.getByRole("menuitem", { name: "Open list view" })).toBeDisabled();
    });

    await test.step("help menu for a schema without documentation, but with list view link", async () => {
      await page.getByText("BuiltinTag", { exact: true }).click();
      await page.getByTestId("schema-help-menu-trigger").click();
      await expect(page.getByRole("menuitem", { name: "Documentation" })).toBeDisabled();
      await expect(page.getByRole("menuitem", { name: "Open list view" })).toBeEnabled();
    });
  });
});
