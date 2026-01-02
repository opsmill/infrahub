import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName, saveScreenshotForDocs } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("/resource-manager - Number Pool Tests", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("number-pool");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("create a new number pool for a generic schema", async ({ page }) => {
    await page.goto(`/resource-manager?branch=${BRANCH_NAME}`);
    await page.getByTestId("create-object-button").click();
    await page.getByLabel("Select an object type").click();
    await page.getByRole("option", { name: "Number Pool Core" }).click();
    await expect(page.getByText("Name *")).toBeVisible();
    await page.getByLabel("Name *").fill("number pool test for generic");
    await page.getByLabel("Node *").click();
    await expect(page.getByRole("option", { name: "Interface Infra", exact: true })).toBeVisible();
    await expect(
      page.getByRole("option", { name: "Artifact Check Core", exact: true })
    ).toBeVisible();
    await page.getByRole("option", { name: "Interface Infra", exact: true }).click();
    await page.getByText("Number Attribute *").click();
    await page.getByRole("option", { name: "Speed" }).click();
    await page.getByLabel("Start range *").fill("1");
    await page.getByLabel("End range *").fill("10");
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.getByText("Number pool created")).toBeVisible();
  });

  test("create a new number pool for a node schema", async ({ page }) => {
    await page.goto(`/resource-manager?branch=${BRANCH_NAME}`);
    await page.getByTestId("create-object-button").click();
    await page.getByLabel("Select an object type").click();
    await page.getByRole("option", { name: "Number Pool Core" }).click();
    await page.getByLabel("Name *").fill("number pool test for node");
    await page.getByLabel("Node *").click();
    await page.getByRole("option", { name: "Interface L3 Infra", exact: true }).click();
    await page.getByText("Number Attribute *").click();
    await page.getByRole("option", { name: "Speed" }).click();
    await page.getByLabel("Start range *").fill("11");
    await page.getByLabel("End range *").fill("20");
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.getByText("Number pool created")).toBeVisible();
  });

  test("displays correct details for a created number pool", async ({ page }) => {
    await page.goto(`/resource-manager?branch=${BRANCH_NAME}`);
    await page
      .getByTestId("object-items")
      .getByRole("link", { name: "number pool test for generic" })
      .click();
    await page.getByRole("cell", { name: "number pool test for generic" }).first().click();
    await expect(page.getByRole("cell", { name: "speed" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "1", exact: true })).toBeVisible();
    await expect(page.getByRole("cell", { name: "10", exact: true })).toBeVisible();
  });

  test("update form should not include node and attribute selects", async ({ page }) => {
    await page.goto(`/resource-manager?branch=${BRANCH_NAME}`);
    await page
      .getByTestId("object-items")
      .getByRole("link", { name: "number pool test for generic" })
      .click();
    await expect(
      page.getByRole("cell", { name: "number pool test for generic" }).first()
    ).toBeVisible();
    await expect(page.getByText("Node *")).not.toBeVisible();
    await expect(page.getByText("Attribute *")).not.toBeVisible();
  });

  test("number pool attribute kind resource manager", async ({ page }) => {
    await page.goto(`/resource-manager?branch=${BRANCH_NAME}`);
    await expect(page.getByRole("link", { name: "InfraService." })).toBeVisible();
    await page.getByRole("link", { name: "InfraService." }).click();
    await page.getByRole("link", { name: "View", exact: true }).click();
    await saveScreenshotForDocs(page, "numberpool_attribute_kind_resource_manager");
  });

  test("create a node using number pool and verify pool assignment", async ({ page }) => {
    await test.step("Navigate to interface creation page", async () => {
      await page.goto(`/objects/InfraInterfaceL3?branch=${BRANCH_NAME}`);
      await page.getByTestId("create-object-button").click();
    });

    await test.step("Fill in interface details", async () => {
      await page.getByRole("combobox", { name: "Device *" }).click();
      await page.getByRole("option", { name: "atl1-core1" }).click();
      await page.getByRole("textbox", { name: "Name *" }).fill("test interface with pool");
    });

    await test.step("Select number pool", async () => {
      await page.getByTestId("number-pool-button").click();
      await expect(
        page.getByRole("option", { name: "number pool test for generic" })
      ).toBeVisible();
      await expect(page.getByRole("option", { name: "number pool test for node" })).toBeVisible();
      await page.getByRole("option", { name: "number pool test for generic" }).click();
      await expect(page.getByTestId("source-pool-badge")).toBeVisible();
    });

    await test.step("Save interface", async () => {
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("InterfaceL3 created")).toBeVisible();
    });

    await test.step("Verify pool assignment", async () => {
      await page.getByRole("searchbox", { name: "Search" }).fill("interface with pool");
      await page.getByRole("link", { name: "test interface with pool" }).click();
      await page.getByText("Speed1").getByTestId("view-metadata-button").click();
      await expect(
        page
          .getByTestId("metadata-tooltip")
          .getByRole("link", { name: "number pool test for generic" })
      ).toBeVisible();
    });
  });
});
