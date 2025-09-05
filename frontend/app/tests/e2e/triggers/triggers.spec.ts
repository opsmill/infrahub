import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("Node Trigger", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  test.describe.configure({ mode: "serial" });

  const BRANCH_NAME = generateRandomBranchName();

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should create a node trigger", async ({ page }) => {
    await test.step("access form", async () => {
      await page.goto(`/objects/CoreTriggerRule?brach=${BRANCH_NAME}`);
      await page.getByTestId("create-object-button").click();
    });

    await test.step("fill and validate form", async () => {
      await page.getByRole("combobox", { name: "Select an object type" }).click();
      await page.getByRole("option", { name: "Node Trigger Rule Core" }).click();
      await page.getByRole("textbox", { name: "Name *" }).fill("test node trigger rule");
      await page.getByRole("combobox", { name: "Node Kind *" }).click();
      await page.getByRole("option", { name: "Device Infra" }).click();
      await page.getByRole("combobox", { name: "Mutation Action *" }).click();
      await page.getByRole("option", { name: "created" }).click();
      await page.getByRole("combobox", { name: "Kind", exact: true }).click();
      await page.getByRole("option", { name: "Group Action Core" }).click();
      await page.getByRole("combobox", { name: "Group Action *" }).click();
      await page.getByRole("button", { name: "+ Add new Group Action" }).click();
      await page.getByRole("textbox", { name: "Name *" }).fill("test group action");
      await page.getByRole("combobox", { name: "Kind" }).click();
      await page.getByRole("option", { name: "Standard Group Core" }).click();
      await page.getByRole("combobox", { name: "Standard Group *" }).click();
      await page.getByRole("button", { name: "+ Add new Standard Group" }).click();
      await page.getByRole("textbox", { name: "Name *" }).fill("test standard group");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("StandardGroup created")).toBeVisible();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("GroupAction created")).toBeVisible();
      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("ensure the creation is correct", async () => {
      await expect(page.getByText("NodeTriggerRule created")).toBeVisible();
      await expect(page.getByRole("link", { name: "test node trigger rule" })).toBeVisible();
    });
  });

  test("should create new matches", async ({ page }) => {
    await test.step("access list view", async () => {
      await page.goto(`/objects/CoreTriggerRule?brach=${BRANCH_NAME}`);
    });

    await test.step("access the matches", async () => {
      await expect(page.getByRole("link", { name: "test node trigger rule" })).toBeVisible();
      await page.getByRole("link", { name: "test node trigger rule" }).click();
      await expect(page.getByText("Nametest node trigger rule")).toBeVisible();
      await page.getByRole("link", { name: "Matches" }).click();
      await expect(page.getByText("No Node Trigger Match found")).toBeVisible();
    });

    await test.step("create an attribute match", async () => {
      await page.getByTestId("open-relationship-form-button").click();
      await page.getByRole("combobox", { name: "Select an object type" }).click();
      await page.getByRole("option", { name: "Node Trigger Attribute Match" }).click();
      await page.getByRole("combobox", { name: "Attribute Name *" }).click();
      await page.getByRole("option", { name: "Name" }).locator("div").nth(1).click();
      await expect(
        page.getByRole("combobox").filter({ hasText: "test node trigger rule" })
      ).toBeVisible();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Node attribute match created!")).toBeVisible();
    });

    await test.step("create a relationship match", async () => {
      await page.getByTestId("open-relationship-form-button").click();
      await page.getByRole("combobox", { name: "Select an object type" }).click();
      await page.getByText("Node Trigger Relationship Match Core").click();
      await page.getByRole("combobox", { name: "Relationship Name *" }).click();
      await page.getByRole("option", { name: "Site" }).click();
      await page.getByRole("combobox", { name: "Peer" }).click();
      await page.getByRole("option", { name: "atl1" }).click();
      await expect(
        page.getByRole("combobox").filter({ hasText: "test node trigger rule" })
      ).toBeVisible();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Node relationship match created!")).toBeVisible();
    });
  });

  test.fixme("should update the matches", async ({ page }) => {
    await test.step("update an attribute match", async () => {
      // The current test id cannot be used for relationsip actions cell
      await page.getByTestId("actions-cell-18462734-cb04-6ee7-3350-c5155d7058b7").click();
      await page.getByRole("menuitem", { name: "Edit" }).click();
      await page.getByRole("combobox", { name: "Attribute Name *" }).click();
      await page.getByRole("option", { name: "Description", exact: true }).click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Node attribute match updated!")).toBeVisible();
    });

    await test.step("update a relationship match", async () => {
      // The current test id cannot be used for relationsip actions cell
      await page.getByTestId("actions-cell-18462759-93ce-7eb1-3357-c51adb1d668e").click();
      await page.getByRole("menuitem", { name: "Edit" }).click();
      await page.getByRole("combobox", { name: "Relationship Name *" }).click();
      await page.getByRole("option", { name: "Asn" }).click();
      await page.getByRole("combobox", { name: "Peer" }).click();
      await page.getByRole("option", { name: "AS174" }).click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Node relationship match")).toBeVisible();
    });
  });
});
