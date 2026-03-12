import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("/object-template - Number pool from template", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  const BRANCH_NAME = generateRandomBranchName("template-number-pool");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("create a number pool for module_capacity", async ({ page }) => {
    await page.goto(`/resource-manager?branch=${BRANCH_NAME}`);
    await expect(page.getByRole("link", { name: "Loopbacks pool" })).toBeVisible();

    await page.getByTestId("create-object-button").click();
    await page.getByLabel("Select an object type").click();
    await page.getByRole("option", { name: "Number Pool Core" }).click();
    await page.getByLabel("Name *").fill("module capacity pool");
    await page.getByLabel("Node *").click();
    await page.getByRole("option", { name: "Patch Panel Infra" }).click();
    await expect(page.getByLabel("Number Attribute *")).toContainText("Module Capacity");
    await page.getByLabel("Start range *").fill("100");
    await page.getByLabel("End range *").fill("200");
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.getByText("Number pool created")).toBeVisible();
  });

  test("should create a patch panel template with number pool for module_capacity", async ({
    page,
  }) => {
    await test.step("Navigate to object templates", async () => {
      await page.goto(`/objects/CoreObjectTemplate?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("heading")).toContainText("Object Template");
    });

    await test.step("Create patch panel template with number pool", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "Patch Panel Infra" }).click();
      await page.getByLabel("Template Name *").fill("number_pool_patch_panel_template");

      await page.getByTestId("number-pool-button").click();
      await page.getByRole("option", { name: "module capacity pool" }).click();
      await expect(page.getByTestId("source-pool-badge")).toBeVisible();
      await expect(page.getByRole("button", { name: "Allocated by pool" })).toBeVisible();

      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("InfraPatchPanel created")).toBeVisible();

      await page.getByRole("link", { name: "number_pool_patch_panel_template" }).click();
      await expect(page.getByText("Module Capacitymodule")).toBeVisible();
    });
  });

  test("should create a patch panel from template with number pool", async ({ page }) => {
    await test.step("Navigate to Patch Panel list", async () => {
      await page.goto(`/objects/InfraPatchPanel?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("heading")).toContainText("Patch Panel");
    });

    await test.step("Create patch panel from template and verify pool is shown", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByRole("button", { name: "Start from template" }).click();
      await page.getByRole("option", { name: "number_pool_patch_panel_template" }).click();
      await expect(page.getByTestId("source-pool-badge")).toBeVisible();
      await expect(page.getByRole("button", { name: "Allocated by pool" })).toBeVisible();

      await page.getByRole("textbox", { name: "Name *" }).fill("patch-panel-from-pool-template");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("PatchPanel created")).toBeVisible();

      await test.step("should show pool-allocated module_capacity on patch panel detail view", async () => {
        await page.getByRole("link", { name: "patch-panel-from-pool-template" }).click();
        await expect(page.getByText("Module Capacity100")).toBeVisible();
        await page
          .getByRole("definition")
          .filter({ hasText: "100" })
          .getByTestId("view-metadata-button")
          .click();
        await expect(page.getByRole("cell", { name: "module capacity pool" })).toBeVisible();
      });
    });
  });
});
