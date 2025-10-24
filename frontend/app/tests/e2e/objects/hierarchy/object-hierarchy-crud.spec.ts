import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../../constants";
import { generateRandomBranchName } from "../../../utils";
import { createBranchAPI, deleteBranchAPI } from "../../utils/graphql";

test.describe("Object hierarchy - Create, Read, Update, Delete operations", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("object-hierarchy-crud");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should perform CRUD operations on hierarchical objects", async ({ page }) => {
    const objectHierarchyTree = page.getByLabel("Hierarchy tree");

    await test.step("should display both tree view and list view for a hierarchical model", async () => {
      await page.goto(`/objects/LocationGeneric?branch=${BRANCH_NAME}`);
      await expect(objectHierarchyTree).toBeVisible();
      await expect(page.getByTestId("object-items")).toBeVisible();
    });

    await test.step("should create a new top level Continent node and verify it appears in the UI", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByRole("combobox", { name: "Select an object type" }).click();
      await page.getByRole("option", { name: "Continent Location" }).click();
      await page.getByRole("textbox", { name: "Name *" }).fill("Test Continent");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Continent created")).toBeVisible();
      await expect(page.getByLabel("Test Continent")).toBeVisible();
    });

    await test.step("should create a child Country node under a collapsed Continent node", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByRole("combobox", { name: "Select an object type" }).click();
      await page.getByRole("option", { name: "Country Location" }).click();
      await page.getByRole("textbox", { name: "Name *" }).fill("Test Country");
      await page.getByRole("combobox", { name: "Parent *" }).click();
      await page.getByRole("option", { name: "Test Continent" }).click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Country created")).toBeVisible();
      await expect(page.getByRole("button", { name: "Expand Test Continent" })).toBeVisible();
    });

    await test.step("should expand parent node to reveal newly created child node", async () => {
      await page.getByRole("button", { name: "Expand Test Continent" }).click();
      await expect(objectHierarchyTree.getByText("Test Country")).toBeVisible();
    });

    await test.step("should update a Country node's name and verify changes in the tree UI", async () => {
      await page.getByTestId("actions-cell-Test Country").click();
      await page.getByRole("menuitem", { name: "Edit" }).click();
      await page.getByRole("textbox", { name: "Name *" }).fill("Test Country updated");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Country updated", { exact: true })).toBeVisible();
      await expect(objectHierarchyTree.getByText("Test Country updated")).toBeVisible();
    });

    await test.step("should create a second Country node under the same Continent parent", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByRole("combobox", { name: "Select an object type" }).click();
      await page.getByRole("option", { name: "Country Location" }).click();
      await page.getByRole("textbox", { name: "Name *" }).fill("Test country 2");
      await page.getByRole("combobox", { name: "Parent *" }).click();
      await page.getByRole("option", { name: "Test Continent" }).click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Country created")).toBeVisible();
      await expect(objectHierarchyTree.getByText("Test country 2")).toBeVisible();
    });

    await test.step("should delete a Country node and verify its removal from the tree", async () => {
      await page.getByTestId("actions-cell-Test country 2").click();
      await page.getByRole("menuitem", { name: "Delete" }).click();
      await page.getByTestId("modal-delete-confirm").click();
      await expect(page.getByText("Object Test country 2 deleted")).toBeVisible();
      await expect(objectHierarchyTree.getByText("Test Country updated")).toBeVisible();
      await expect(objectHierarchyTree.getByText("Test Country 2")).not.toBeVisible();
    });
  });
});
