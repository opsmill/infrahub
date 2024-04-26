import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../../constants";

test.describe("/objects/CoreProfile - Profiles page", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("should create a new profile successfully", async ({ page }) => {
    await test.step("Navigate to CoreProfile page", async () => {
      await page.goto("/objects/CoreProfile");
      await expect(page.getByRole("heading")).toContainText("Profile");
    });

    await test.step("Create a new profile", async () => {
      await page.getByTestId("create-object-button").click();
      await page
        .getByTestId("side-panel-container")
        .getByTestId("select-open-option-button")
        .click();
      await page.getByRole("option", { name: "ProfileBuiltinTag" }).click();
      await page.getByLabel("Profile Name *").fill("profile test tag");
      await page.getByLabel("Description").fill("A profile for E2E test");
      await page.getByRole("button", { name: "Create" }).click();
    });

    await test.step("Verify profile creation success", async () => {
      await expect(
        page.locator("#alert-success-BuiltinTag-created").getByText("BuiltinTag created")
      ).toBeVisible();
      await expect(page.getByRole("link", { name: "ProfileBuiltinTag" })).toBeVisible();
      await expect(page.getByRole("link", { name: "profile test tag" })).toBeVisible();
    });
  });

  test("should access the profile created and view its data", async ({ page }) => {
    await test.step("Navigate to CoreProfile page", async () => {
      await page.goto("/objects/CoreProfile");
      await expect(page.getByRole("heading")).toContainText("Profile");
      await page.getByRole("link", { name: "profile test tag" }).click();
    });

    await expect(page.getByText("Profile Nameprofile test tag")).toBeVisible();
    await expect(page.getByText("Name-")).toBeVisible();
    await expect(page.getByText("DescriptionA profile for E2E")).toBeVisible();

    await test.step("return to profiles list using breadcrumb", async () => {
      await page.getByRole("main").getByRole("link", { name: "All Profiles" }).click();
      expect(page.url()).toContain("/objects/CoreProfile");
    });
  });

  test("create an object with a profile", async ({ page }) => {
    await test.step("Navigate to object creation page", async () => {
      await page.goto("/objects/BuiltinTag");
      await page.getByTestId("create-object-button").click();
    });

    await test.step("Select profile and enter details", async () => {
      await page
        .getByTestId("side-panel-container")
        .getByTestId("select-open-option-button")
        .click();
      await page.getByRole("option", { name: "profile test tag" }).click();

      // Verify initial input fields for profile
      await expect(page.getByLabel("Name *")).toBeEmpty();
      await expect(page.getByLabel("Description")).toHaveValue("A profile for E2E test");

      await page.getByLabel("Name *").fill("tag with profile");
      await page.getByRole("button", { name: "Create" }).click();
    });

    await test.step("Verify object creation", async () => {
      await expect(page.locator("#alert-success-Tag-created")).toContainText("Tag created");
      await page.getByRole("link", { name: "tag with profile" }).click();
    });

    await test.step("Verify profile metadata", async () => {
      await page.getByText("Nametag with profile").getByTestId("view-metadata-button").click();
      await expect(page.getByTestId("metadata-tooltip").getByText("Source-")).toBeVisible();
      await page.getByText("Nametag with profile").getByTestId("view-metadata-button").click(); // to close popover
      await page
        .getByText("DescriptionA profile for E2E")
        .getByTestId("view-metadata-button")
        .click();
      await expect(
        page.getByTestId("metadata-tooltip").getByText("Sourceprofile test tag")
      ).toBeVisible();
    });

    await test.step("Verify profile link", async () => {
      await page.getByRole("link", { name: "profile test tag" }).click();
      expect(page.url()).toContain("/objects/ProfileBuiltinTag");
    });
  });

  test("should delete the profile", async ({ page }) => {
    await test.step("Navigate to CoreProfile page", async () => {
      await page.goto("/objects/CoreProfile");
    });

    await test.step("Delete the profile", async () => {
      await page
        .getByRole("row", { name: "ProfileBuiltinTag profile" })
        .getByTestId("delete-row-button")
        .click();
      await expect(page.getByTestId("modal-delete")).toContainText(
        "Are you sure you want to remove the object `profile test tag`?"
      );
      await page.getByTestId("modal-delete-confirm").click();
    });

    await test.step("Verify profile deletion", async () => {
      await expect(page.getByText("Object profile test tag")).toBeVisible();
    });
  });
});
