import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../../constants";
import { generateRandomBranchName } from "../../../utils";
import { createBranchAPI, deleteBranchAPI } from "../../utils/graphql";

const PROFILE_NAME = "Interface L2 profile test";
const GENERIC_PROFILE_NAME = "Generic Interface profile test";

test.describe("/objects/CoreProfile - Profile for Interface L2 and fields verification", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName();

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should verify the form fields for a new profile for interface L2", async ({ page }) => {
    await test.step("access Interface L2 form", async () => {
      await page.goto(`/objects/CoreProfile?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("link", { name: "backbone_profile" })).toBeVisible();

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
      ).toBeVisible();
      await expect(page.getByLabel("Device *")).not.toBeVisible();
    });
  });

  test("should create a new profile successfully for interface L2", async ({ page }) => {
    await test.step("access Interface L2 form", async () => {
      await page.goto(`/objects/CoreProfile?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("link", { name: "backbone_profile" })).toBeVisible();
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
      await page.goto(`/objects/CoreProfile?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("link", { name: "backbone_profile" })).toBeVisible();
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
    await page.goto(`/objects/CoreProfile?branch=${BRANCH_NAME}`);
    await page.getByRole("link", { name: PROFILE_NAME }).click();
    await expect(page.getByText("Profile NameInterface L2")).toBeVisible();
    await expect(page.getByText("Profile Priority2000")).toBeVisible();
    await expect(page.getByText("MTU256")).toBeVisible();
    await expect(
      page
        .locator("div")
        .filter({ hasText: /^Enabled$/ })
        .locator("svg")
        .first()
    ).toBeVisible();
    await expect(page.getByText("Provisioning", { exact: true })).toBeVisible();
  });

  test("should verify the available profiles in the object form", async ({ page }) => {
    await page.goto(`/objects/InfraInterface?branch=${BRANCH_NAME}`);
    await expect(
      page.getByRole("link", { name: "atl1-edge1, Ethernet1", exact: true })
    ).toBeVisible();
    await page.getByTestId("create-object-button").click();
    await page.getByLabel("Select an object type").click();
    await page.getByRole("option", { name: "Interface L2 Infra", exact: true }).click();
    await page.getByLabel("Select profiles optional").click();
    await expect(page.getByText(PROFILE_NAME, { exact: true })).toBeVisible();
    await expect(page.getByText(GENERIC_PROFILE_NAME)).toBeVisible();
  });
});
