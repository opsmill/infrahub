import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("object-template", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("object-template");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should create nodes from a template", async ({ page }) => {
    await test.step("should create profile first", async () => {
      await page.goto(`/objects/CoreProfile?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("heading", { name: "Profile" })).toBeVisible();
      await expect(page.getByRole("link", { name: "upstream_profile" })).toBeVisible();
      await page.getByTestId("create-object-button").click();

      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "Patch Panel Infra" }).click();

      await page.getByLabel("Profile Name *").fill("Profile for patch panel");

      await page.getByLabel("Module Capacity").fill("1000");

      await page.getByLabel("Description").fill("Description from profile");

      await page.getByRole("button", { name: "Save" }).click();

      await expect(page.getByText("InfraPatchPanel created")).toBeVisible();
      await expect(page.getByRole("link", { name: "Profile for patch panel" })).toBeVisible();
    });

    await test.step("should create a template with the profile", async () => {
      await page.goto(`/objects/CoreObjectTemplate?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("heading", { name: "Object Templates" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Regular_Patch_Panel" })).toBeVisible();
      await page.getByTestId("create-object-button").click();

      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "Patch Panel Infra" }).click();

      await page.getByLabel("Select profiles optional").click();
      await page.getByRole("option", { name: "Profile for patch panel" }).click();

      await expect(page.getByTestId("source-profile-badge").first()).toBeVisible();
      await expect(page.getByRole("textbox", { name: "Description" })).toHaveValue(
        "Description from profile"
      );

      await page.getByLabel("Template Name *").fill("Template with profile");
      await page.getByLabel("Module Capacity").fill("2000");
      await page.getByRole("button", { name: "Save" }).click();

      await expect(page.getByText("InfraPatchPanel created")).toBeVisible();
      await expect(page.getByRole("link", { name: "Template with profile" })).toBeVisible();
    });

    await test.step("should create a node from the template", async () => {
      await page.goto(`/objects/InfraPatchPanel?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("heading", { name: "Patch Panel" })).toBeVisible();
      await page.getByTestId("create-object-button").click();

      await page.getByRole("button", { name: "Start from template Pick a" }).click();
      await page.getByRole("option", { name: "Template with profile" }).click();
      await expect(page.getByTestId("source-template-badge")).toBeVisible();
      await expect(page.getByTestId("source-profile-badge")).toBeVisible();
      await expect(page.getByRole("textbox", { name: "Description" })).toHaveValue(
        "Description from profile"
      );
      await expect(page.getByLabel("Module Capacity")).toHaveValue("2000");
      await page.getByLabel("Name *").fill("Test from template and profile");
      await page.getByRole("button", { name: "Save" }).click();

      await expect(page.getByText("PatchPanel created")).toBeVisible();
      await expect(
        page.getByRole("link", { name: "Test from template and profile" })
      ).toBeVisible();
      await expect(page.getByText("2000")).toBeVisible();
      await expect(page.getByText("Description from profile")).toBeVisible();
    });
  });
});
