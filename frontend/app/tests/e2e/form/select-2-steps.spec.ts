import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

const BRANCH_NAME = "select-2-steps";

test.describe("Verifies the object creation", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("verifies empty values after kind select", async ({ page }) => {
    await page.goto(`/objects/CoreGraphQLQuery?branch=${BRANCH_NAME}`);
    await page.getByTestId("create-object-button").click();
    await page.getByLabel("Kind").click();
    await page.getByRole("option", { name: "Repository Core", exact: true }).click();
    await page.getByLabel("Repository").click();
    await expect(page.getByText("Read-Only Repository", { exact: true })).not.toBeVisible();
  });

  test("verifies values in kind and parent selects", async ({ page }) => {
    await test.step("got to the edit form", async () => {
      await page.goto(`/objects/InfraInterfaceL3?branch=${BRANCH_NAME}`);
      await page
        .getByTestId("identifier-cell")
        .getByRole("link", { name: "dfw1-edge1, Ethernet1", exact: true })
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
