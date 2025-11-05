import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../../constants";
import { generateRandomBranchName } from "../../../utils";
import { createBranchAPI, deleteBranchAPI } from "../../utils/graphql";

test.describe("Object hierarchy- Navigation", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("object-hierarchy-navigation");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should display correctly", async ({ page }) => {
    const objectHierarchyTree = page.getByLabel("Hierarchy tree");

    await test.step("view tree and list for a hierarchical model", async () => {
      await page.goto(`/objects/LocationGeneric?branch=${BRANCH_NAME}`);
      await expect(objectHierarchyTree).toBeVisible();
      await expect(page.getByTestId("object-items")).toBeVisible();
    });

    await test.step("display every node type when model is a generic", async () => {
      await expect(page.getByTestId("object-items")).toContainText("Continent");
      await expect(page.getByTestId("object-items")).toContainText("Country");
    });

    await test.step("clicking on a tree chevron should should open tree but not redirect page", async () => {
      await page.getByRole("button", { name: "Expand North America" }).click();
      await expect(objectHierarchyTree.getByText("Canada")).toBeVisible();
      await expect(objectHierarchyTree.getByText("United States of America")).toBeVisible();
      await expect(page.getByTestId("object-items")).toBeVisible();
    });

    await test.step("navigate using tree should not expand tree", async () => {
      await objectHierarchyTree.getByText("United States of America").click();
      await expect(page.getByText("NameUnited States of America")).toBeVisible();
      await expect(page.getByText("Children5")).toBeVisible();
      await expect(
        objectHierarchyTree.getByRole("row", { name: "United States of America" })
      ).toContainClass("bg-neutral-100");
      await expect(
        objectHierarchyTree.getByRole("button", { name: "Expand United States of" })
      ).toBeVisible();
    });

    await test.step("navigate on right panel should not change the tree", async () => {
      await objectHierarchyTree.getByText("North America").click();
      await expect(page.getByText("NameNorth America")).toBeVisible();
      await expect(
        objectHierarchyTree.getByRole("button", { name: "Collapse North America" })
      ).toBeVisible();
      await expect(
        objectHierarchyTree.getByRole("button", { name: "Expand United States of" })
      ).toBeVisible();
      await expect(objectHierarchyTree.getByRole("row", { name: "North America" })).toContainClass(
        "bg-neutral-100"
      );
    });
  });
});
