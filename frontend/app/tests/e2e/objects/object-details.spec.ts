import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("/objects/:objectKind/:objectId", () => {
  const BRANCH_NAME = generateRandomBranchName("object-details");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test.describe("when not logged in", () => {
    test("should not be able to edit object", async ({ page }) => {
      await page.goto(`/objects/InfraBGPSession?branch=${BRANCH_NAME}`);
      await page.getByRole("link", { name: "203.111.0.2/29, atl1-edge1" }).click();

      await expect(page.getByTestId("edit-button")).toBeDisabled();
      await expect(page.getByTestId("manage-groups")).toBeDisabled();
    });
  });

  test.describe("when logged in as Admin", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should be able to edit object", async ({ page }) => {
      await page.goto(`/objects/InfraBGPSession?branch=${BRANCH_NAME}`);

      await page.getByRole("link", { name: "203.111.0.2/29, atl1-edge1" }).click();

      await expect(page.getByTestId("edit-button")).toBeEnabled();
      await expect(page.getByTestId("manage-groups")).toBeEnabled();
    });

    test("should display relationships correctly", async ({ page }) => {
      await page.goto(`/objects/InfraBGPSession?branch=${BRANCH_NAME}`);

      await page.getByRole("link", { name: "203.111.0.2/29, atl1-edge1" }).click();

      // Attribute
      await expect(page.getByText("Type", { exact: true })).toBeVisible();
      await expect(page.getByText("Description", { exact: true })).toBeVisible();
      await expect(page.getByText("Import Policies", { exact: true })).toBeVisible();
      await expect(page.getByText("Export Policies", { exact: true })).toBeVisible();
      await expect(page.getByText("Status", { exact: true })).toBeVisible();
      await expect(page.getByText("Role", { exact: true })).toBeVisible();

      // Relationships Attributes
      await expect(page.getByText("Local As", { exact: true })).toBeVisible();
      await expect(page.getByText("Remote As", { exact: true })).toBeVisible();
      await expect(page.getByText("Local Ip", { exact: true })).toBeVisible();
      await expect(page.getByText("Remote Ip", { exact: true })).toBeVisible();
      await expect(page.getByText("Peer Group", { exact: true })).toBeVisible();
      await expect(page.getByText("Peer Session", { exact: true })).toBeVisible();

      // Relationships Generics
      await expect(page.getByTestId("object-details").getByText("Device")).toBeVisible();
    });

    test("should display the select 2 steps correctly", async ({ page }) => {
      await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);

      await page.getByRole("link", { name: "atl1-edge1" }).click();
      await page.getByText("Interfaces15").click();
      await page.getByRole("link", { name: "Ethernet4" }).first().click();
      await page.getByTestId("edit-button").click();

      const kindSelector = page.getByLabel("Kind").getByTestId("select-value");
      await expect(kindSelector).toContainText("Circuit Endpoint");

      const nodeSelector = page.getByLabel("Circuit Endpoint").getByTestId("select-value");
      await expect(nodeSelector).not.toBeEmpty(); // ID is in the input but it's dynamic
    });

    test("should display node metadata popover", async ({ page }) => {
      await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);

      await page.getByRole("link", { name: "atl1-edge1" }).click();

      await page.getByTestId("node-metadata-button").click();

      await expect(page.getByText("Created at")).toBeVisible();
      await expect(page.getByText("Created by")).toBeVisible();
      await expect(page.getByText("Updated at")).toBeVisible();
      await expect(page.getByText("Updated by")).toBeVisible();
    });
  });
});
