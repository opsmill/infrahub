import { expect, test } from "@playwright/test";

import { saveScreenshotForDocs } from "../../utils";

test.describe("/schema - Schema visualizer", () => {
  test("redirect to schema page using object help menu", async ({ page }) => {
    await page.goto("/objects/InfraInterface");
    await page.getByRole("button", { name: "?" }).click();
    await page.getByRole("menuitem", { name: "Schema" }).click();
    await expect(page.getByTestId("schema-viewer")).toBeVisible();
    await expect(page.getByText("KindInfraInterface")).toBeVisible();
    await expect(page).toHaveURL(/\/schema\?kind=InfraInterface/);
  });

  test("display help menu correctly", async ({ page }) => {
    await page.goto("/schema");

    await test.step("open schema viewer", async () => {
      await page.getByText("CoreGraphQL Query", { exact: true }).click();
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

    await test.step("close menu when pressing Esc", async () => {
      await page.locator("body").press("Escape");
      await expect(page.getByTestId("schema-help-menu-content")).not.toBeVisible();
    });

    await test.step("help menu for a schema without documentation not list view link", async () => {
      await page.getByText("CoreThread - Artifact").click();
      await page.getByTestId("schema-help-menu-trigger").click();
      await expect(page.getByRole("menuitem", { name: "Documentation" })).toBeDisabled();
      await expect(page.getByRole("menuitem", { name: "Open list view" })).toBeDisabled();
      await page.locator("body").press("Escape");
    });

    await test.step("help menu for a schema without documentation, but with list view link", async () => {
      await page.getByText("BuiltinTag", { exact: true }).click();
      await page.getByTestId("schema-help-menu-trigger").click();
      await expect(page.getByRole("menuitem", { name: "Documentation" })).toBeDisabled();
      await expect(page.getByRole("menuitem", { name: "Open list view" })).toBeEnabled();
    });
  });

  test("filter schema list", async ({ page }) => {
    await page.goto("/schema");
    await expect(page.getByRole("heading", { name: "Core Account Node" })).toBeVisible();

    await page.getByPlaceholder("Search schema").fill("tag");
    await expect(page.getByRole("heading", { name: "Builtin Tag Node" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Core Account Node" })).not.toBeVisible();
  });

  test("view schema attribute kind numberpool", async ({ page }) => {
    await page.goto("/schema");
    await page.getByPlaceholder("Search schema").fill("InfraBackBoneService");
    await page.getByText("InfraBackbone Service").click();
    await page.getByRole("tab", { name: "Attributes" }).click();
    await page.getByText("Service Identifier NumberPool").click();
    await page.getByText("Parameters").click();
    await saveScreenshotForDocs(page, "schema_numberpool");
  });
});
