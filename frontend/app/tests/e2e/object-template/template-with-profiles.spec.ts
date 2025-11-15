import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../../constants";
import { generateRandomBranchName } from "../../../utils";
import { createBranchAPI, deleteBranchAPI } from "../../utils/graphql";

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

  test("should create a profile for templates", async ({ page }) => {
    await test.step("Navigate to CoreProfile page", async () => {
      await page.goto(`/objects/CoreProfile?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("heading")).toContainText("Profile");
    });

    await test.step("Create a rack profile", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "Rack" }).click();
      await page.getByLabel("Profile Name *").fill("standard_rack_profile");
      await page.getByLabel("Profile Priority *").fill("100");
      await page.getByLabel("Description").fill("Standard 42U rack configuration");
      await page.getByLabel("Height").fill("42");
      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("Verify profile creation", async () => {
      await expect(page.getByRole("link", { name: "standard_rack_profile" })).toBeVisible();
    });
  });

  test("should create a template and assign profile to it", async ({ page }) => {
    await test.step("Navigate to Rack templates", async () => {
      await page.goto(`/objects/CoreObjectTemplate?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("heading")).toContainText("Object Template");
    });

    await test.step("Create rack template", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "Rack" }).click();
      await page.getByLabel("Template Name *").fill("datacenter_rack_template");
      await page.getByLabel("Name").fill("DC-RACK");
      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("Verify template creation", async () => {
      await expect(
        page.locator("#alert-success-InfraRack-created").getByText("InfraRack created")
      ).toBeVisible();
    });

    await test.step("Navigate back and access template", async () => {
      await page.goto(`/objects/CoreObjectTemplate?branch=${BRANCH_NAME}`);
      await page.getByRole("link", { name: "datacenter_rack_template" }).click();
    });

    await test.step("Assign profile to template", async () => {
      await page.getByTestId("object-header-edit-button").click();
      await page.getByLabel("Select profiles").click();
      await page.getByRole("option", { name: "standard_rack_profile" }).click();
      await page.getByLabel("Select profiles").click(); // Close dropdown

      // Verify profile value appears
      await expect(page.getByLabel("Height")).toHaveValue("42");

      // Check profile badge shows
      const heightInput = page.locator('input[name="height"]').locator("..");
      await expect(heightInput.getByTestId("source-profile-badge")).toBeVisible();
      await expect(heightInput.getByTestId("source-profile-badge")).toContainText(
        "standard_rack_profile"
      );

      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("Verify profile is assigned", async () => {
      await expect(
        page.locator("#alert-success-Rack-updated").getByText("Rack updated")
      ).toBeVisible();

      // Check that height shows with profile source
      await expect(page.getByText("Height42")).toBeVisible();
      await page.getByText("Height42").getByTestId("view-metadata-button").click();
      await expect(page.getByTestId("metadata-tooltip")).toContainText("standard_rack_profile");
    });
  });

  test("should create object from template with profile and inherit profile values", async ({
    page,
  }) => {
    await test.step("Navigate to Rack objects", async () => {
      await page.goto(`/objects/InfraRack?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("heading")).toContainText("Rack");
    });

    await test.step("Create rack from template", async () => {
      await page.getByTestId("create-object-button").click();

      // Select template
      await expect(page.getByRole("button", { name: "Start from template" })).toBeVisible();
      await page.getByRole("button", { name: "Start from template" }).click();
      await page.getByRole("option", { name: "datacenter_rack_template" }).click();

      // Verify form is populated from template
      await expect(page.getByLabel("Name *")).toHaveValue("DC-RACK");

      // Verify height is populated from profile (not editable by default)
      await expect(page.getByLabel("Height")).toHaveValue("42");

      // Check profile badge
      const heightInput = page.locator('input[name="height"]').locator("..");
      await expect(heightInput.getByTestId("source-profile-badge")).toBeVisible();

      // Set unique name
      await page.getByLabel("Name *").fill("RACK-01");
      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("Verify object creation and profile inheritance", async () => {
      await expect(page.locator("#alert-success-Rack-created")).toContainText("Rack created");

      // Navigate to object details
      await page.getByRole("link", { name: "RACK-01" }).click();

      // Verify height value from profile
      await expect(page.getByText("Height42")).toBeVisible();

      // Check metadata shows profile as source
      await page.getByText("Height42").getByTestId("view-metadata-button").click();
      await expect(page.getByTestId("metadata-tooltip")).toContainText("standard_rack_profile");
      await expect(page.getByTestId("metadata-tooltip").getByText("is_from_profile")).toBeVisible();
    });
  });

  test("should show profile values override template values", async ({ page }) => {
    await test.step("Create template with its own height value", async () => {
      await page.goto(`/objects/CoreObjectTemplate?branch=${BRANCH_NAME}`);
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "Rack" }).click();
      await page.getByLabel("Template Name *").fill("custom_height_template");
      await page.getByLabel("Name").fill("CUSTOM-RACK");
      await page.getByLabel("Height").fill("48"); // Template sets height to 48
      await page.getByRole("button", { name: "Save" }).click();

      await expect(
        page.locator("#alert-success-InfraRack-created").getByText("InfraRack created")
      ).toBeVisible();
    });

    await test.step("Navigate to template and add profile", async () => {
      await page.goto(`/objects/CoreObjectTemplate?branch=${BRANCH_NAME}`);
      await page.getByRole("link", { name: "custom_height_template" }).click();

      // Verify template has height 48
      await expect(page.getByText("Height48")).toBeVisible();

      await page.getByTestId("object-header-edit-button").click();

      // Add profile
      await page.getByLabel("Select profiles").click();
      await page.getByRole("option", { name: "standard_rack_profile" }).click();
      await page.getByLabel("Select profiles").click();

      // Height should now show 42 from profile (not 48 from template)
      await expect(page.getByLabel("Height")).toHaveValue("42");

      // Profile badge should be visible
      const heightInput = page.locator('input[name="height"]').locator("..");
      await expect(heightInput.getByTestId("source-profile-badge")).toBeVisible();

      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("Verify profile overrode template value", async () => {
      await expect(
        page.locator("#alert-success-Rack-updated").getByText("Rack updated")
      ).toBeVisible();

      // Height should now be 42 (from profile), not 48 (from template's original value)
      await expect(page.getByText("Height42")).toBeVisible();

      // Verify source is profile
      await page.getByText("Height42").getByTestId("view-metadata-button").click();
      await expect(page.getByTestId("metadata-tooltip")).toContainText("standard_rack_profile");
      await expect(page.getByTestId("metadata-tooltip").getByText("is_from_profile")).toBeVisible();
    });

    await test.step("Create object from template and verify profile precedence", async () => {
      await page.goto(`/objects/InfraRack?branch=${BRANCH_NAME}`);
      await page.getByTestId("create-object-button").click();

      await page.getByRole("button", { name: "Start from template" }).click();
      await page.getByRole("option", { name: "custom_height_template" }).click();

      // Should get height from profile (42), not template's original value (48)
      await expect(page.getByLabel("Height")).toHaveValue("42");

      await page.getByLabel("Name *").fill("RACK-02");
      await page.getByRole("button", { name: "Save" }).click();

      await expect(page.locator("#alert-success-Rack-created")).toContainText("Rack created");

      await page.getByRole("link", { name: "RACK-02" }).click();

      // Verify height is 42 from profile
      await expect(page.getByText("Height42")).toBeVisible();

      await page.getByText("Height42").getByTestId("view-metadata-button").click();
      await expect(page.getByTestId("metadata-tooltip")).toContainText("standard_rack_profile");
    });
  });

  test("should support multiple profiles on template with priority", async ({ page }) => {
    await test.step("Create second profile with lower priority", async () => {
      await page.goto(`/objects/CoreProfile?branch=${BRANCH_NAME}`);
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "Rack" }).click();
      await page.getByLabel("Profile Name *").fill("low_priority_rack_profile");
      await page.getByLabel("Profile Priority *").fill("200"); // Lower priority (higher number)
      await page.getByLabel("Height").fill("36");
      await page.getByRole("button", { name: "Save" }).click();

      await expect(page.getByRole("link", { name: "low_priority_rack_profile" })).toBeVisible();
    });

    await test.step("Create template with both profiles", async () => {
      await page.goto(`/objects/CoreObjectTemplate?branch=${BRANCH_NAME}`);
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "Rack" }).click();
      await page.getByLabel("Template Name *").fill("multi_profile_template");
      await page.getByLabel("Name").fill("MULTI-RACK");

      // Add both profiles
      await page.getByLabel("Select profiles").click();
      await page.getByRole("option", { name: "standard_rack_profile" }).click();
      await page.getByRole("option", { name: "low_priority_rack_profile" }).click();
      await page.getByLabel("Select profiles").click();

      // Should show height from higher priority profile (lower number = higher priority)
      await expect(page.getByLabel("Height")).toHaveValue("42"); // From standard_rack_profile (priority 100)

      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("Verify higher priority profile wins", async () => {
      await expect(
        page.locator("#alert-success-InfraRack-created").getByText("InfraRack created")
      ).toBeVisible();

      await page.goto(`/objects/CoreObjectTemplate?branch=${BRANCH_NAME}`);
      await page.getByRole("link", { name: "multi_profile_template" }).click();

      // Height should be 42 from higher priority profile
      await expect(page.getByText("Height42")).toBeVisible();

      await page.getByText("Height42").getByTestId("view-metadata-button").click();
      await expect(page.getByTestId("metadata-tooltip")).toContainText("standard_rack_profile");
    });
  });
});
