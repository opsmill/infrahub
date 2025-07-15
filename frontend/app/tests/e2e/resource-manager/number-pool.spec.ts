import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName, saveScreenshotForDocs } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("/resource-manager - Resource Manager", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("number-pool");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should create a new pool", async ({ page }) => {
    await page.goto(`/resource-manager?branch=${BRANCH_NAME}`);
    await page.getByTestId("create-object-button").click();
    await page.getByLabel("Select an object type").click();
    await page.getByRole("option", { name: "Number Pool Core" }).click();
    await expect(page.getByText("Name *")).toBeVisible();
    await page.getByLabel("Name *").fill("number pool test");
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

  test("pool details should be correct", async ({ page }) => {
    await page.goto(`/resource-manager?branch=${BRANCH_NAME}`);
    await page.getByTestId("object-items").getByRole("link", { name: "number pool test" }).click();
    await page.getByRole("cell", { name: "number pool test" }).first().click();
    await expect(page.getByRole("cell", { name: "speed" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "1", exact: true })).toBeVisible();
    await expect(page.getByRole("cell", { name: "10", exact: true })).toBeVisible();
  });

  test("update form should not include node and attribute selects", async ({ page }) => {
    await page.goto(`/resource-manager?branch=${BRANCH_NAME}`);
    await page.getByTestId("object-items").getByRole("link", { name: "number pool test" }).click();
    await expect(page.getByRole("cell", { name: "number pool test" }).first()).toBeVisible();
    await expect(page.getByText("Node *")).not.toBeVisible();
    await expect(page.getByText("Attribute *")).not.toBeVisible();
  });

  test("numberpool attribute kind resource manager", async ({ page }) => {
    await page.goto(`/resource-manager?branch=${BRANCH_NAME}`);
    await expect(page.getByRole("link", { name: "InfraService." })).toBeVisible();
    await page.getByRole("link", { name: "InfraService." }).click();
    await page.getByRole("link", { name: "View", exact: true }).click();
    await saveScreenshotForDocs(page, "numberpool_attribute_kind_resource_manager");
  });
});
