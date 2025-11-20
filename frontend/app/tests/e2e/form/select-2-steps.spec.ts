import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("Verifies the object creation", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  test.describe.configure({ mode: "serial" });

  const BRANCH_NAME = generateRandomBranchName("select-2-steps");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("creates and verifies the nodes values", async ({ page }) => {
    await test.step("create the object", async () => {
      await page.goto(`/objects/InfraVLAN?branch=${BRANCH_NAME}`);
      await page.getByTestId("create-object-button").click();
      await page.getByRole("combobox", { name: "Site" }).click();
      await page.getByRole("option", { name: "atl1" }).click();
      await page.getByRole("textbox", { name: "Name *" }).fill("vlan-test");
      await page.getByRole("spinbutton", { name: "Vlan Id *" }).fill("600");
      await page.getByRole("combobox", { name: "Device" }).click();
      await page.getByRole("option", { name: "atl1-core1" }).click();
      await page.getByRole("combobox", { name: "L3 Gateway" }).click();
      await page.getByRole("option", { name: "MGMT" }).click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("VLAN created")).toBeVisible();
    });

    await test.step("verify object details", async () => {
      await page.getByRole("link", { name: "vlan-test" }).click();
      await expect(page.getByText("Namevlan-test")).toBeVisible();
      await expect(page.getByText("Vlan Id600")).toBeVisible();
      await expect(page.getByText("L3 GatewayMGMT")).toBeVisible();
    });

    await test.step("verify initial values", async () => {
      await page.getByTestId("edit-button").click();
      await expect(page.getByRole("combobox", { name: "Device" })).toBeVisible();
      await expect(page.getByRole("combobox", { name: "L3 Gateway" })).toBeVisible();
    });
  });

  test("verifies empty values after kind select", async ({ page }) => {
    await page.goto(`/objects/CoreGraphQLQuery?branch=${BRANCH_NAME}`);
    await page.getByTestId("create-object-button").click();
    await page.getByRole("combobox", { name: "Kind" }).click();
    await page.getByRole("option", { name: "Repository Core", exact: true }).click();
    await page.getByLabel("Repository").click();
    await expect(page.getByText("Read-Only Repository", { exact: true })).not.toBeVisible();
  });

  test("verifies values in kind and parent selects", async ({ page }) => {
    await test.step("got to the edit form", async () => {
      await page.goto(`/objects/InfraInterfaceL3?branch=${BRANCH_NAME}`);
      await page
        .getByTestId("identifier-cell")
        .getByRole("link", { name: "Ethernet1", exact: true })
        .first()
        .click();
      await page.getByTestId("edit-button").click();
    });

    await test.step("check inputs values", async () => {
      await expect(page.getByLabel("Kind")).toContainText("Interface L3 Infra");
      await expect(page.locator('button[name="connected_endpoint_parent"]')).toContainText(
        "dfw1-edge2"
      );
      await expect(
        page.getByTestId("side-panel-container").getByLabel("Interface L3")
      ).toContainText("Ethernet1");

      await page.getByTestId("side-panel-container").getByLabel("Interface L3").click();
      await expect(page.getByRole("option", { name: "Ethernet10" })).toBeVisible();
      await expect(page.getByRole("option", { name: "Loopback0" })).toBeVisible();
      await expect(page.getByRole("option", { name: "Management0" })).toBeVisible();
    });
  });
});
