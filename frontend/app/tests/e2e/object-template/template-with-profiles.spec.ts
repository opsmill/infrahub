import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("/object-template - Template with Profiles", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  const BRANCH_NAME = generateRandomBranchName("template-profiles");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("should create a device profile for templates", async ({ page }) => {
    await test.step("Navigate to CoreProfile page", async () => {
      await page.goto(`/objects/CoreProfile?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("heading")).toContainText("Profile");
    });

    await test.step("Create a device profile", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "Device" }).click();
      await page.getByLabel("Profile Name *").fill("device_spine_profile");
      await page.getByRole("combobox", { name: "Status" }).click();
      await page
        .locator("div")
        .filter({ hasText: /^Active$/ })
        .click();
      await page.getByRole("combobox", { name: "Role" }).click();
      await page
        .locator("div")
        .filter({ hasText: /^Spine Router$/ })
        .click();
      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("Verify profile creation", async () => {
      await expect(page.getByRole("link", { name: "device_spine_profile" })).toBeVisible();
    });
  });

  test("should create a template and assign profile to it", async ({ page }) => {
    await test.step("Navigate to device templates", async () => {
      await page.goto(`/objects/CoreObjectTemplate?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("heading")).toContainText("Object Template");
    });

    await test.step("Create device template", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "Device" }).click();
      await expect(page.getByRole("button", { name: "Select profiles optional" })).toBeVisible();
      await page.getByRole("button", { name: "Select profiles optional" }).click();
      await page.getByRole("option", { name: "device_spine_profile" }).click();
      await expect(page.getByTestId("source-profile-badge").first()).toBeVisible();
      await page.getByTestId("source-profile-badge").nth(1).click();
      await page.getByRole("textbox", { name: "Template Name *" }).fill("device_spine_template");
      await page.getByRole("combobox", { name: "Platform" }).click();
      await page.getByText("Cisco IOS", { exact: true }).click();
      await page.getByRole("textbox", { name: "Type" }).fill("spine");

      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("Verify template creation", async () => {
      await expect(
        page.locator("#alert-success-InfraDevice-created").getByText("InfraDevice created")
      ).toBeVisible();
    });

    await test.step("Navigate back and access template", async () => {
      await page.goto(`/objects/CoreObjectTemplate?branch=${BRANCH_NAME}`);
      await page.getByRole("link", { name: "device_spine_template" }).click();
    });

    await test.step("Verify profile is assigned to template", async () => {
      await page
        .getByRole("definition")
        .filter({ hasText: "Active" })
        .getByTestId("view-metadata-button")
        .click();
      await expect(
        page.getByTestId("metadata-tooltip").getByRole("link", { name: "device_spine_profile" })
      ).toBeVisible();
    });
  });

  test("should create object from template with profile and inherit profile values", async ({
    page,
  }) => {
    await test.step("Navigate to Device objects", async () => {
      await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("heading")).toContainText("Device");
    });

    await test.step("Create device from template", async () => {
      await page.getByTestId("create-object-button").click();

      // Select template
      await expect(page.getByRole("button", { name: "Start from template" })).toBeVisible();
      await page.getByRole("button", { name: "Start from template" }).click();
      await page.getByRole("option", { name: "device_spine_template" }).click();

      // Verify profile is shown as selected
      await expect(page.getByRole("button", { name: "Select profiles optional" })).toBeVisible();
      await expect(page.getByText("device_spine_profile×")).toBeVisible();

      // Verify form is populated from template/profile
      await expect(page.getByLabel("Status")).toContainText("Active");
      await expect(page.getByLabel("Role")).toContainText("Spine Router");

      // Check profile badges
      await expect(page.getByTestId("source-profile-badge").first()).toBeVisible();
      await expect(page.getByTestId("source-profile-badge").nth(1)).toBeVisible();

      await page.getByRole("textbox", { name: "Name *" }).fill("spine-router-01");
      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("Navigate to object details", async () => {
      await expect(page.locator("#alert-success-Device-created")).toContainText("Device created");
      await page.getByRole("link", { name: "spine-router-01" }).click();
    });

    await test.step("Verify inherited profile values", async () => {
      await page
        .getByRole("definition")
        .filter({ hasText: "Active" })
        .getByTestId("view-metadata-button")
        .click();
      await expect(
        page.getByTestId("metadata-tooltip").getByRole("link", { name: "device_spine_profile" })
      ).toBeVisible();
    });
  });
});
