import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../../constants";

const PROFILE_NAME = "Interface L2 profile test";

test.describe("/objects/CoreProfile - Profiles page", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should verify the form fields for a new profile for interface L2", async ({ page }) => {
    await test.step("access Interface L2 form", async () => {
      await page.goto("/objects/CoreProfile");
      await page.getByTestId("create-object-button").click();
      await page.getByTestId("side-panel-container").getByTestId("select-input").fill("l2");
      await page.getByText("ProfileInfraInterfaceL2").click();
    });

    await test.step("check fields", async () => {
      await expect(page.getByText("Profile Name *")).toBeVisible();
      await expect(page.getByText("Description")).toBeVisible();
      await expect(page.getByText("MTU")).toBeVisible();
      await expect(page.getByText("Enabled")).toBeVisible();
      await expect(page.getByText("Status")).toBeVisible();
      await expect(page.getByText("Role")).toBeVisible();
    });
  });

  test("should verify that some fields are not displayed (no mandatory nor relationships fields)", async ({
    page,
  }) => {
    await test.step("access Interface L2 form", async () => {
      await page.goto("/objects/CoreProfile");
      await page.getByTestId("create-object-button").click();
      await page.getByTestId("side-panel-container").getByTestId("select-input").fill("l2");
      await page.getByText("ProfileInfraInterfaceL2").click();
    });

    await test.step("check fields", async () => {
      await expect(page.getByText("Layer2 Mode *")).not.toBeVisible();
      await expect(page.getByText("Speed *")).not.toBeVisible();
      await expect(page.getByText("Untagged VLAN")).not.toBeVisible();
      await expect(
        page.getByTestId("side-panel-container").getByText("Tagged VLANs")
      ).not.toBeVisible();
      await expect(page.getByText("Device *")).not.toBeVisible();
    });
  });

  test("should create a new profile successfully for interface L2", async ({ page }) => {
    await test.step("access Interface L2 form", async () => {
      await page.goto("/objects/CoreProfile");
      await page.getByTestId("create-object-button").click();
      await page.getByTestId("side-panel-container").getByTestId("select-input").fill("l2");
      await page.getByText("ProfileInfraInterfaceL2").click();
    });

    await test.step("fill and submit form", async () => {
      await page.getByLabel("Profile Name *").fill(PROFILE_NAME);
      await page.getByLabel("Profile Priority").fill("2000");
      await page.getByLabel("MTU").fill("256");
      await page.getByLabel("Enabled").check();
      await page
        .locator("div:below(:text('Status'))")
        .first()
        .getByTestId("select-open-option-button")
        .click();
      await page.getByText("Provisioning").click();
      await page.getByRole("button", { name: "Create" }).click();
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
});
