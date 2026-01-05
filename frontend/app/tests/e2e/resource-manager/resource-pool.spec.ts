import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/resource-manager - Resource Manager", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("create a new pool", async ({ page }) => {
    await page.goto("/resource-manager");
    await expect(page.getByRole("link", { name: "External prefixes pool" })).toBeVisible();
    await page.getByTestId("create-object-button").click();

    await page.getByLabel("Select an object type").click();

    await page.getByRole("option", { name: "IP Prefix Pool Core" }).click();

    await page.getByLabel("Name *").fill("test prefix pool");
    await page.getByLabel("Resources *").click();
    await page.getByRole("option", { name: "10.0.0.0/8" }).click();
    await page.getByRole("option", { name: "10.0.0.0/16" }).click();
    await page.getByRole("option", { name: "10.1.0.0/16" }).click();
    await expect(page.getByLabel("Default Prefix Type")).toContainText("IP PrefixIpam");
    await page.getByLabel("Resources *").click();

    await page.getByLabel("IPAM Namespace *").click();
    await page.getByRole("option", { name: "default" }).click();
    await page.getByRole("button", { name: "Save" }).click();

    await expect(page.getByText("IP prefix pool created")).toBeVisible();
    await expect(page.getByRole("link", { name: "test prefix pool" })).toBeVisible();
  });

  test("see details and edit a pool", async ({ page }) => {
    await page.goto("/resource-manager");
    await page.getByRole("link", { name: "test prefix pool" }).click();

    await expect(page.getByText("Core IP Prefix Pool")).toBeVisible();
    await expect(page.getByText("Nametest prefix pool")).toBeVisible();
    await expect(page.getByText("Description-")).toBeVisible();
    expect(page.url()).toContain("/resource-manager/");

    await page.getByTestId("edit-button").click();
    await expect(page.getByLabel("Default Prefix Type")).toContainText("IP PrefixIpam");
    await page.getByLabel("Description").fill("a test pool for e2e");
    await page.getByRole("button", { name: "Save" }).click();

    await expect(page.getByText("IPPrefixPool updated")).toBeVisible();
    await expect(page.getByText("Descriptiona test pool for e2e")).toBeVisible();
  });

  test("delete a pool", async ({ page }) => {
    await page.goto("/resource-manager");

    await page.getByTestId("actions-cell-test prefix pool").click();
    await page.getByRole("menuitem", { name: "Delete" }).click();
    await expect(page.getByText("Are you sure you want to remove test prefix pool?")).toBeVisible();
    await page.getByTestId("modal-delete-confirm").click();

    await expect(page.getByText("Object test prefix pool")).toBeVisible();
    await expect(page.getByRole("link", { name: "test prefix pool" })).toBeHidden();
  });
});
