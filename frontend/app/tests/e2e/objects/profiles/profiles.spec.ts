import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../../constants";

const PROFILE_NAME = "Interface L2 profile test";
const GENERIC_PROFILE_NAME = "Generic Interface profile test";

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
      await page.goto("/objects/CoreProfile");
      await expect(page.getByRole("heading")).toContainText("Profile");
      await page.getByRole("link", { name: "profile test tag" }).click();
    });

    await expect(page.getByText("Profile Nameprofile test tag")).toBeVisible();
    await expect(page.getByText("Profile Priority1000")).toBeVisible();
    await expect(page.getByText("DescriptionA profile for E2E")).toBeVisible();

    await test.step("return to profiles list using breadcrumb", async () => {
      await page.getByTestId("object-header").getByRole("link", { name: "All Profiles" }).click();
      expect(page.url()).toContain("/objects/CoreProfile");
    });
  });

  test("create an object with a profile", async ({ page }) => {
    await test.step("Navigate to object creation page", async () => {
      await page.goto("/objects/BuiltinTag");
      await page.getByTestId("create-object-button").click();
    });

    await test.step("Select profile and enter details", async () => {
      await page.getByLabel("Select profiles").click();
      await page.getByRole("option", { name: "profile test tag" }).click();

      // Verify initial input fields for profile
      await expect(page.getByLabel("Name *")).toBeEmpty();
      await expect(page.getByLabel("Description")).toHaveValue("A profile for E2E test");

      await expect(page.getByTestId("source-profile-badge")).toBeVisible();
      await expect(page.getByTestId("source-profile-badge")).toContainText("profile test tag");
      await page.getByLabel("Select profiles").click();
      await page.getByTestId("source-profile-badge").hover();
      await expect(page.getByTestId("source-profile-tooltip").first()).toBeVisible();
      await expect(page.getByRole("link", { name: "profile test tag" }).first()).toBeVisible();
      await page.locator("body").press("Escape"); // hide tooltip

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
        page.getByTestId("metadata-tooltip").getByText("Sourceprofile test tag")
      ).toBeVisible();
    });

    await test.step("Verify profile link", async () => {
      await page.getByRole("link", { name: "profile test tag" }).click();
      expect(page.url()).toContain("/objects/ProfileBuiltinTag/");
    });
  });

  test("edit a used profile and verify the changes reflect in an object using it", async ({
    page,
  }) => {
    await test.step("Navigate to an used profile", async () => {
      await page.goto("/objects/CoreProfile");
      await expect(page.getByRole("heading")).toContainText("Profile");
      await page.getByRole("link", { name: "profile test tag" }).click();
    });

    await test.step("Edit the profile", async () => {
      await page.getByTestId("edit-button").click();
      await page.getByLabel("Description").fill("A profile for E2E test edited");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("DescriptionA profile for E2E test")).toBeVisible();
    });

    await test.step("Verify the changes in an object using the edited profile", async () => {
      await page.goto("/objects/BuiltinTag");
      await page.getByRole("link", { name: "tag with profile" }).click();
      await expect(page.getByText("DescriptionA profile for E2E test")).toBeVisible();
    });
  });

  test("edit profile of tag without touching any other field", async ({ page }) => {
    await test.step("got to edit form of tag", async () => {
      await page.goto("/objects/BuiltinTag");
      await page.getByRole("link", { name: "tag with profile" }).click();
      await page.getByTestId("edit-button").click();
    });

    await test.step("remove profile from tag", async () => {
      await page.getByLabel("Select profiles optional").click();
      await page.getByRole("option", { name: "profile test tag" }).click();
      await expect(page.getByLabel("Description")).toBeEmpty();
      await page.getByRole("button", { name: "Save" }).click();
    });

    await expect(page.getByText("Description-")).toBeVisible();
  });

  test("delete the profile and reset object attribute value", async ({ page }) => {
    await test.step("Navigate to CoreProfile page", async () => {
      await page.goto("/objects/CoreProfile");
    });

    await test.step("Delete the profile", async () => {
      await page
        .getByRole("row", { name: "ProfileBuiltinTag profile" })
        .getByTestId("delete-row-button")
        .click();
      await expect(page.getByTestId("modal-delete")).toContainText(
        'Are you sure you want to remove the Profile"profile test tag"?'
      );
      await page.getByTestId("modal-delete-confirm").click();
    });

    await test.step("Verify profile deletion", async () => {
      await expect(page.getByText("Object profile test tag deleted")).toBeVisible();
    });

    await test.step("Object attribute using profile value should be reset", async () => {
      await page.goto("/objects/BuiltinTag");
      await page.getByRole("link", { name: "tag with profile" }).click();
      await expect(page.getByText("Description-")).toBeVisible();
      await page.getByText("Description-").getByTestId("view-metadata-button").click();
      await expect(page.getByTestId("metadata-tooltip").getByText("Source-")).toBeVisible();
    });
  });
});

test.describe("/objects/CoreProfile - Profile for Interface L2 and fields verification", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("should verify the form fields for a new profile for interface L2", async ({ page }) => {
    await test.step("access Interface L2 form", async () => {
      await page.goto("/objects/CoreProfile");

      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "Interface L2 Infra", exact: true }).click();
    });

    await test.step("verify Interface L2 optional attributes are all visible", async () => {
      await expect(page.getByLabel("Profile Name *")).toBeVisible();
      await expect(page.getByLabel("Description")).toBeVisible();
      await expect(page.getByLabel("MTU")).toBeVisible();
      await expect(page.getByLabel("Enabled")).toBeVisible();
      await expect(page.getByLabel("Status")).toBeVisible();
      await expect(page.getByLabel("Role")).toBeVisible();
    });

    await test.step("verify Interface L2 mandatory attributes and relationships are not visible", async () => {
      await expect(page.getByLabel("Layer2 Mode *")).not.toBeVisible();
      await expect(page.getByLabel("Speed *")).not.toBeVisible();
      await expect(page.getByLabel("Untagged VLAN")).not.toBeVisible();
      await expect(
        page.getByTestId("side-panel-container").getByText("Tagged VLANs")
      ).not.toBeVisible();
      await expect(page.getByLabel("Device *")).not.toBeVisible();
    });
  });

  test("should create a new profile successfully for interface L2", async ({ page }) => {
    await test.step("access Interface L2 form", async () => {
      await page.goto("/objects/CoreProfile");
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "Interface L2 Infra", exact: true }).click();
    });

    await test.step("fill and submit form", async () => {
      await page.getByLabel("Profile Name *").fill(PROFILE_NAME);
      await page.getByLabel("Profile Priority").fill("2000");
      await page.getByLabel("MTU").fill("256");
      await page.getByLabel("Enabled").check();
      await page.getByLabel("Status").click();
      await page.getByText("Provisioning").click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("InfraInterfaceL2 created")).toBeVisible();
    });
  });

  test("should create a new profile successfully for generic interface", async ({ page }) => {
    await test.step("access Interface form", async () => {
      await page.goto("/objects/CoreProfile");
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "Interface Infra", exact: true }).click();
    });

    await test.step("fill and submit form", async () => {
      await page.getByLabel("Profile Name *").fill(GENERIC_PROFILE_NAME);
      await page.getByLabel("Profile Priority").fill("2000");
      await page.getByLabel("Status").click();
      await page.getByText("Maintenance", { exact: true }).click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("InfraInterface created")).toBeVisible();
    });
  });

  test("should verify profile values after creation", async ({ page }) => {
    await page.goto("/objects/CoreProfile");
    await page.getByRole("link", { name: PROFILE_NAME }).click();
    await expect(page.locator("dl").getByText(PROFILE_NAME)).toBeVisible();
    await expect(page.getByText("2000")).toBeVisible();
    await expect(page.getByText("256")).toBeVisible();
    await expect(
      page
        .locator("div")
        .filter({ hasText: /^Enabled$/ })
        .locator("svg")
        .first()
    ).toBeVisible();
    await expect(page.getByText("Provisioning")).toBeVisible();
  });

  test("should verify the available profiles in the object form", async ({ page }) => {
    await page.goto("/objects/InfraInterface");
    await page.getByTestId("create-object-button").click();
    await page.getByLabel("Select an object type").click();
    await page.getByRole("option", { name: "Interface L2 Infra", exact: true }).click();
    await page.getByLabel("Select profiles optional").click();
    await expect(page.getByText(PROFILE_NAME)).toBeVisible();
    await expect(page.getByText(GENERIC_PROFILE_NAME)).toBeVisible();
  });
});
