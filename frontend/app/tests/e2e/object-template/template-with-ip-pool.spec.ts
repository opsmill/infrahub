import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("/object-template - Pool from template", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  const BRANCH_NAME = generateRandomBranchName("template-pool");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should create a device template with pool for primary_address", async ({ page }) => {
    await test.step("Navigate to object templates", async () => {
      await page.goto(`/objects/CoreObjectTemplate?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("heading")).toContainText("Object Template");
    });

    await test.step("Create device template with pool allocation for primary_address", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Select an object type").click();
      await page.getByRole("option", { name: "Device Infra" }).click();
      await page.getByLabel("Template Name *").fill("pool_device_template");

      await page.getByTestId("select-open-pool-option-button").click();
      await page.getByRole("option", { name: "Loopbacks pool" }).click();
      await expect(page.getByTestId("source-pool-badge")).toBeVisible();
      await expect(page.getByLabel("Primary_Address")).toContainText("Allocated by pool");

      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("InfraDevice created")).toBeVisible();
    });
  });

  test("should not include template pool values in create mutation", async ({ page }) => {
    await test.step("Navigate to Device list", async () => {
      await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);
      await expect(page.getByRole("heading")).toContainText("Device");
    });

    await test.step("Create device from template and verify mutation excludes pool data", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByRole("button", { name: "Start from template" }).click();
      await page.getByRole("option", { name: "pool_device_template" }).click();
      await expect(page.getByTestId("source-pool-badge")).toBeVisible();
      await expect(page.getByLabel("Primary IP Address")).toContainText("Loopbacks pool");

      await page.getByRole("textbox", { name: "Name *" }).fill("device-from-pool-template");
      await page.getByRole("textbox", { name: "Type *" }).fill("test type");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Device created")).toBeVisible();
    });
  });

  test("should show pool-allocated primary address on device detail view", async ({ page }) => {
    await test.step("Navigate to created device", async () => {
      await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);
      await page.getByRole("link", { name: "device-from-pool-template" }).click();
    });

    await test.step("Verify primary address was allocated from pool", async () => {
      await expect(page.getByText("Primary IP Address10.0.0.")).toBeVisible(); // The allocated IP should be visible as a link
    });
  });
});
