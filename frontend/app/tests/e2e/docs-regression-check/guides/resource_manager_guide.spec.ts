import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../../constants";
import { saveScreenshotForDocs } from "../../../utils";

test.describe.fixme("Guide - Resources Manager", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("IP Address Pool", async ({ page }) => {
    await test.step("Create prefix 10.100.0.0/24", async () => {
      await page.goto("/ipam");
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Prefix *").fill("10.100.0.0/24");
      await saveScreenshotForDocs(
        page,
        "guides/resources-manager/resource_manager_rss_prefix_10_100_0"
      );
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("IPPrefix created")).toBeVisible();
    });

    await test.step("Create IP Pool - 10.100.0.0/24", async () => {
      await page.goto("/resource-manager");
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "IP Address Pool Core" }).click();

      await page.getByRole("textbox", { name: "Name *" }).fill("My IP address pool");
      await page.getByRole("spinbutton", { name: "Default Prefix Length" }).fill("24");
      await page
        .getByTestId("side-panel-container")
        .locator("div")
        .filter({ hasText: "Resources *" })
        .first()
        .click();
      await page.locator("form").getByPlaceholder("Filter...").fill("10.100.0");
      await page.getByRole("option", { name: "10.100.0.0/" }).click();
      await page
        .locator("div")
        .filter({ hasText: /^Resources \*$/ })
        .click();

      await page.getByRole("combobox", { name: "IPAM Namespace *" }).click();
      await page.getByRole("option", { name: "default" }).click();

      await saveScreenshotForDocs(page, "guides/resources-manager/resource_manager_pool_ip");
      await page.getByRole("button", { name: "Save" }).click();

      await expect(page.getByText("IP address pool created")).toBeVisible();
    });

    await test.step("Use Pool to allocate IP on Device", async () => {
      await page.goto("/objects/InfraDevice");
      await page.getByTestId("create-object-button").click();
      await page.getByRole("combobox", { name: "Site" }).click();
      await page.getByRole("option", { name: "atl1" }).click();
      await page.getByRole("textbox", { name: "Name *" }).fill("dev-123");
      await page.getByRole("textbox", { name: "Type *" }).fill("MX204");
      await page.getByTestId("select-open-pool-option-button").click();
      await expect(page.getByRole("option", { name: "My IP address pool" })).toBeVisible();
      await saveScreenshotForDocs(
        page,
        "guides/resources-manager/resource_manager_pool_device_before"
      );
      await page.getByRole("option", { name: "My IP address pool" }).click();
      await saveScreenshotForDocs(
        page,
        "guides/resources-manager/resource_manager_pool_device_after"
      );
      await page.getByRole("button", { name: "Save" }).click();
    });
  });

  test("IP Prefix Pool", async ({ page }) => {
    await test.step("Create prefix 10.100.1.0/24", async () => {
      await page.goto("/ipam");
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Prefix *").fill("10.100.1.0/24");
      await page.getByRole("combobox", { name: "Member Type" }).click();
      await page
        .locator("div")
        .filter({ hasText: /^Prefix$/ })
        .click();
      await saveScreenshotForDocs(
        page,
        "guides/resources-manager/resource_manager_rss_prefix_10_100_1"
      );
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("IPPrefix created")).toBeVisible();
    });

    await test.step("Create Prefix Pool - 10.100.1.0/24", async () => {
      await page.goto("/resource-manager");
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "IP Prefix Pool Core" }).click();

      await page.getByRole("textbox", { name: "Name *" }).fill("Customer Service Pool");
      await page.getByLabel("Default Prefix Length").fill("31");

      await page
        .getByTestId("side-panel-container")
        .locator("div")
        .filter({ hasText: "Resources *" })
        .first()
        .click();
      await page.locator("form").getByPlaceholder("Filter...").fill("10.100.1");
      await page.getByRole("option", { name: "10.100.1.0/" }).click();
      await page
        .locator("div")
        .filter({ hasText: /^Resources \*$/ })
        .click();

      await page.getByRole("combobox", { name: "IPAM Namespace *" }).click();
      await page.getByRole("option", { name: "default" }).click();

      await saveScreenshotForDocs(page, "guides/resources-manager/resource_manager_pool_prefix");
      await page.getByRole("button", { name: "Save" }).click();
    });

    // TODO: Allocating an IP prefix to a relationship of a node - Need #5888
  });

  test("Number Pool", async ({ page }) => {
    await test.step("Create Number Pool - VLAN ID", async () => {
      await page.goto("/resource-manager");
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "Number Pool Core" }).click();
      await page.getByLabel("Name *").fill("My VLAN ID Pool");
      await page.getByLabel("Node *").click();
      const filterInput = page.getByPlaceholder("Filter...").nth(1);
      await filterInput.fill("VLAN");
      await page.getByText("VLAN Infra").click();
      await expect(page.getByLabel("Number Attribute *")).toContainText("Vlan Id");
      await page.getByRole("spinbutton", { name: "Start range *" }).fill("100");
      await page.getByRole("spinbutton", { name: "End range *" }).fill("1000");
      await saveScreenshotForDocs(page, "guides/resources-manager/resource_manager_pool_vlan");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Number pool created")).toBeVisible();
    });

    await test.step("Use Pool to allocate ID to VLAN", async () => {
      await page.goto("/objects/InfraVLAN");
      await page.getByTestId("create-object-button").click();
      await page.getByRole("textbox", { name: "Name *" }).fill("My vlan");
      await page.getByTestId("number-pool-button").click();
      await expect(page.getByRole("option", { name: "My VLAN ID Pool" })).toBeVisible();
      await saveScreenshotForDocs(
        page,
        "guides/resources-manager/resource_manager_pool_vlan_before"
      );
      await page.getByRole("option", { name: "My VLAN ID Pool" }).click();
      await saveScreenshotForDocs(
        page,
        "guides/resources-manager/resource_manager_pool_vlan_after"
      );
      await page.getByRole("button", { name: "Save" }).click();
    });
  });
});
