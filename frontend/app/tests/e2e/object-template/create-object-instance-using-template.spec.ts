import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe.fixme("object-template", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should create nodes from a template", async ({ page }) => {
    await test.step("should create profile first", async () => {
      await page.goto("/objects/CoreProfile");
      await expect(page.getByRole("heading", { name: "Profile" })).toBeVisible();
      await page.getByTestId("create-object-button").click();

      await page.getByRole("combobox", { name: "Select an object type" }).click();
      await page.getByRole("option", { name: "Patch Panel Infra" }).click();

      await page.getByRole("textbox", { name: "Profile Name *" }).fill("Profile for patch panel");

      await page.getByRole("spinbutton", { name: "Module Capacity" }).fill("1000");

      await page.getByRole("textbox", { name: "Description" }).fill("Description from profile");

      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("InfraPatchPanel created")).toBeVisible();
      await expect(page.getByRole("link", { name: "Profile for patch panel" })).toBeVisible();
    });

    await test.step("should create a template with the profile", async () => {
      await page.goto("/objects/CoreObjectTemplate");
      await expect(page.getByRole("heading", { name: "Object Templates" })).toBeVisible();
      await page.getByTestId("create-object-button").click();
      await page.getByRole("combobox", { name: "Select an object type" }).click();
      await page.getByRole("option", { name: "Patch Panel Infra" }).click();
      await page.getByRole("button", { name: "Select profiles optional" }).click();
      await page.getByRole("option", { name: "Profile for patch panel" }).click();
      await expect(page.getByTestId("source-profile-badge").first()).toBeVisible();
      await expect(page.getByRole("textbox", { name: "Description" })).toHaveValue(
        "Description from profile"
      );
      await page.getByRole("textbox", { name: "Template Name *" }).fill("Template with profile");
      // Override module capacity
      await page.getByRole("spinbutton", { name: "Module Capacity" }).fill("2000");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("InfraPatchPanel created")).toBeVisible();
      await expect(page.getByRole("link", { name: "Template with profile" })).toBeVisible();
    });

    await test.step("should create a node from the template", async () => {
      await page.goto("http://localhost:8080/objects/InfraPatchPanel");
      await expect(page.getByRole("heading", { name: "Patch Panel" })).toBeVisible();
      await page.getByTestId("create-object-button").click();
      await page.getByRole("button", { name: "Start from template Pick a" }).click();
      await page.getByRole("option", { name: "Template with profile" }).click();
      await expect(page.getByTestId("source-template-badge")).toBeVisible();
      await expect(page.getByTestId("source-profile-badge")).toBeVisible();
      await expect(page.getByRole("textbox", { name: "Description" })).toHaveValue(
        "Description from profile"
      );
      await expect(page.getByRole("spinbutton", { name: "Module Capacity" })).toHaveValue("2000");
      await page.getByRole("textbox", { name: "Name *" }).click();
      await page.getByRole("textbox", { name: "Name *" }).fill("Test from template and profile");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("PatchPanel created")).toBeVisible();
      await expect(
        page.getByRole("link", { name: "Test from template and profile" })
      ).toBeVisible();
      await expect(
        page.locator("span").filter({ hasText: "Test from template and profile" })
      ).toBeVisible();
      await expect(page.getByText("2000")).toBeVisible();
      await expect(page.getByText("Description from profile")).toBeVisible();
    });
  });
});
