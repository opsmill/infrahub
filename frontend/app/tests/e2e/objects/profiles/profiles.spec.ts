import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../../constants";
import { generateRandomBranchName } from "../../../utils";
import { createBranchAPI, deleteBranchAPI } from "../../utils/graphql";

test.describe("/objects/CoreProfile - Profiles page", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  const BRANCH_NAME = generateRandomBranchName("profiles");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should create a new profile successfully", async ({ page }) => {
    await test.step("Navigate to CoreProfile page", async () => {
      await page.goto(`/objects/CoreProfile?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("heading")).toContainText("Profile");
      await expect(page.getByRole("link", { name: "upstream_profile" })).toBeVisible();
    });

    await test.step("Create a new profile", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "Tag Builtin" }).click();
      await page.getByLabel("Profile Name *").fill("profile test tag");
      await page.getByLabel("Description").fill("A profile for E2E test");
      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("Verify profile creation success", async () => {
      await expect(
        page.locator("#alert-success-BuiltinTag-created").getByText("BuiltinTag created")
      ).toBeVisible();
      await expect(page.getByRole("link", { name: "profile test tag" })).toBeVisible();
    });
  });

  test("access the created profile, view its data, and edit it", async ({ page }) => {
    await test.step("Navigate to CoreProfile page", async () => {
      await page.goto(`/objects/CoreProfile?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("heading")).toContainText("Profile");
      const profileLink = page.getByRole("link", { name: "profile test tag" });
      await expect(profileLink).toBeVisible({ timeout: 30_000 });
      await page.getByRole("link", { name: "profile test tag" }).click();
    });

    await expect(page.getByText("Profile Nameprofile test tag")).toBeVisible();
    await expect(page.getByText("Profile Priority1000")).toBeVisible();
    await expect(page.getByText("DescriptionA profile for E2E")).toBeVisible();

    await test.step("return to profiles list using breadcrumb", async () => {
      await page
        .getByTestId("breadcrumb-navigation")
        .getByRole("link", { name: "Profile", exact: true })
        .click();
      await expect(page.getByRole("heading", { name: "Profile" })).toBeVisible();
      expect(page.url()).toContain("/objects/CoreProfile");
    });
  });

  test("create an object with a profile", async ({ page }) => {
    await test.step("Navigate to object creation page", async () => {
      await page.goto(`/objects/BuiltinTag?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("link", { name: "blue" })).toBeVisible();
      await page.getByTestId("create-object-button").click();
    });

    await test.step("Select profile and enter details", async () => {
      await page.getByLabel("Select profiles").click();
      const profileOption = page.getByRole("option", { name: "profile test tag" });
      await expect(profileOption).toBeVisible({ timeout: 30_000 });
      await page.getByRole("option", { name: "profile test tag" }).click();
      await page.getByLabel("Select profiles").click();

      // Verify initial input fields for profile
      await expect(page.getByLabel("Name *")).toBeEmpty();
      await expect(page.getByLabel("Description")).toHaveValue("A profile for E2E test");

      await expect(page.getByTestId("source-profile-badge")).toBeVisible();
      await expect(page.getByTestId("source-profile-badge")).toContainText("profile test tag");
      await page.getByTestId("source-profile-badge").hover();
      await expect(page.getByTestId("source-profile-tooltip").first()).toBeVisible();
      await expect(page.getByRole("link", { name: "profile test tag" }).first()).toBeVisible();
      await page.getByLabel("Name *").click(); // hide tooltip

      await page.getByLabel("Name *").fill("tag with profile");
      await page.getByRole("button", { name: "Save" }).click();
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
        page.getByTestId("metadata-tooltip").getByRole("link", { name: "profile test tag" })
      ).toBeVisible();
    });

    await test.step("Verify profile link", async () => {
      await page
        .getByTestId("metadata-tooltip")
        .getByRole("link", { name: "profile test tag" })
        .click();
      expect(page.url()).toContain("/objects/ProfileBuiltinTag/");
    });
  });

  test("edit a used profile and verify the changes reflect in an object using it", async ({
    page,
  }) => {
    await test.step("Navigate to an used profile", async () => {
      await page.goto(`/objects/CoreProfile?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("heading")).toContainText("Profile");
      await page.getByRole("link", { name: "profile test tag" }).click();
    });

    await test.step("Edit the profile", async () => {
      await page.getByTestId("edit-button").click();
      await page.getByLabel("Description").fill("A profile for E2E test edited");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("DescriptionA profile for E2E test edited")).toBeVisible();
    });

    await test.step("Verify the changes in an object using the edited profile", async () => {
      await page.goto(`/objects/BuiltinTag?branch=${BRANCH_NAME}`);
      await page.getByRole("link", { name: "tag with profile" }).click();
      await expect(page.getByRole("heading", { name: "tag with profile" })).toBeVisible();

      // Refresh profile is an async task
      while (await page.getByText("DescriptionA profile for E2E test edited").isHidden()) {
        await page.reload();
        await expect(page.getByText("DescriptionA profile for E2E test")).toBeVisible();
      }
    });
  });

  test("edit profile of tag without touching any other field", async ({ page }) => {
    await test.step("got to edit form of tag", async () => {
      await page.goto(`/objects/BuiltinTag?branch=${BRANCH_NAME}`);
      await page.getByRole("link", { name: "tag with profile" }).click();
      await page.getByTestId("edit-button").click();
    });

    await test.step("remove profile from tag", async () => {
      await page.getByText("profile test tag×").getByTestId("remove-option").click();
      await expect(page.getByLabel("Description")).toBeEmpty();
      await page.getByRole("button", { name: "Save" }).click();
    });

    await expect(page.getByTestId("object-details").getByText("Description-")).toBeVisible();
  });

  test("delete the profile and reset object attribute value", async ({ page }) => {
    await test.step("Navigate to CoreProfile page", async () => {
      await page.goto(`/objects/CoreProfile?branch=${BRANCH_NAME}`);
    });

    await test.step("Delete the profile", async () => {
      await page.getByTestId("actions-cell-profile test tag").click();
      await page.getByRole("menuitem", { name: "Delete" }).click();
      await expect(page.getByTestId("modal-delete")).toContainText(
        "Are you sure you want to remove profile test tag?"
      );
      await page.getByTestId("modal-delete-confirm").click();
    });

    await test.step("Verify profile deletion", async () => {
      await expect(page.getByText("Object profile test tag deleted")).toBeVisible();
    });

    await test.step("Object attribute using profile value should be reset", async () => {
      await page.goto(`/objects/BuiltinTag?branch=${BRANCH_NAME}`);
      await page.getByRole("link", { name: "tag with profile" }).click();
      await expect(page.getByText("Description-", { exact: true })).toBeVisible();
      await page.getByText("Description-").getByTestId("view-metadata-button").click();
      await expect(page.getByTestId("metadata-tooltip").getByText("Source-")).toBeVisible();
    });
  });
});
