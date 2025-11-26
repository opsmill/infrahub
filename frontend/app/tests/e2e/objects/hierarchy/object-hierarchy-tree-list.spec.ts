import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../../constants";
import { generateRandomBranchName } from "../../../utils";
import { createBranchAPI, deleteBranchAPI } from "../../utils/graphql";

test.describe("Object hierarchy tree lite - Focused tree view", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("object-hierarchy-tree-lite");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should display lite tree on initial load and refresh on node changes", async ({ page }) => {
    const objectHierarchyTree = page.getByLabel("Hierarchy tree", { exact: true });
    const objectHierarchyTreeLite = page.getByLabel("Hierarchy tree lite");

    await test.step("navigate to a child node in the hierarchy", async () => {
      await page.goto(`/objects/LocationGeneric?branch=${BRANCH_NAME}`);
      await expect(objectHierarchyTree).toBeVisible();
      await page.getByRole("button", { name: "Expand North America" }).click();
      await objectHierarchyTree.getByText("United States of America").click();
      await expect(
        page.getByTestId("object-header").getByText("United States of America")
      ).toBeVisible();
    });

    await test.step("reload page - lite tree should appear on initial load", async () => {
      await page.reload();
      await expect(objectHierarchyTreeLite).toBeVisible();
      await expect(objectHierarchyTree).not.toBeVisible();
    });

    await test.step("verify lite tree shows parent, current node highlighted, and siblings", async () => {
      await expect(page.getByRole("button", { name: "Back" })).toBeVisible();
      await expect(objectHierarchyTreeLite.getByText("North America")).toBeVisible();
      await expect(
        objectHierarchyTreeLite.getByRole("row", { name: "United States of America" })
      ).toContainClass("bg-neutral-100");
      await expect(objectHierarchyTreeLite.getByText("Canada")).toBeVisible();
    });

    await page.getByTestId("breadcrumb-navigation").getByRole("link", { name: "Country" }).click();

    await test.step("add a sibling node - lite tree should refresh", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByRole("textbox", { name: "Name *" }).fill("Country 1");
      await page.getByRole("combobox", { name: "Parent *" }).click();
      await page.getByRole("option", { name: "North America" }).click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("Country created")).toBeVisible();
      await expect(objectHierarchyTreeLite.getByText("Country 1")).toBeVisible();
    });

    await test.step("add another sibling node - lite tree should refresh", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByRole("textbox", { name: "Name *" }).fill("country 2");
      await page.getByRole("combobox", { name: "Parent *" }).click();
      await page.getByRole("option", { name: "North America" }).click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(objectHierarchyTreeLite.getByText("country 2")).toBeVisible();
    });

    await test.step("delete a sibling node - lite tree should refresh", async () => {
      await page.getByTestId("actions-cell-country 2").click();
      await page.getByRole("menuitem", { name: "Delete" }).click();
      await page.getByTestId("modal-delete-confirm").click();
      await expect(objectHierarchyTreeLite.getByText("Country 1")).toBeVisible();
      await expect(objectHierarchyTreeLite.getByText("country 2")).not.toBeVisible();
    });

    await test.step("navigate to sibling via lite tree", async () => {
      await objectHierarchyTreeLite.getByText("Country 1").click();
      await expect(page.getByTestId("object-header").getByText("Country 1")).toBeVisible();
    });

    await test.step("click Back button - should show full tree", async () => {
      await page.getByRole("button", { name: "Back" }).click();
      await expect(objectHierarchyTree).toBeVisible();
      await expect(objectHierarchyTreeLite).not.toBeVisible();
    });

    await test.step("delete current node - should fall back to full tree", async () => {
      await page.reload();
      await expect(page.getByTestId("object-header").getByText("Country 1")).toBeVisible();
      await expect(objectHierarchyTreeLite).toBeVisible();
      await expect(objectHierarchyTree).not.toBeVisible();

      await page.getByTestId("delete-button").click();
      await page.getByTestId("modal-delete-confirm").click();
      await expect(page.getByText("Object Country 1 deleted")).toBeVisible();

      // After deleting the current node, should fall back to full tree (not show error)
      await expect(objectHierarchyTree).toBeVisible();
      await expect(objectHierarchyTreeLite).not.toBeVisible();
    });
  });
});
