import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("Object hierarchical view", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should display correctly", async ({ page }) => {
    await test.step("view tree and list for a hierarchical model", async () => {
      await page.goto("/objects/LocationGeneric");
      await expect(page.getByTestId("hierarchical-tree")).toBeVisible();
      await expect(page.getByTestId("object-items")).toBeVisible();
    });

    await test.step("display every node type when model is a generic", async () => {
      await expect(page.getByTestId("object-items")).toContainText("Continent");
      await expect(page.getByTestId("object-items")).toContainText("Country");
    });

    await test.step("clicking on a tree chevron should should open tree but not redirect page", async () => {
      await page
        .getByRole("treeitem", { name: "North America" })
        .getByTestId("tree-item-toggle")
        .click();

      await expect(page.getByRole("treeitem", { name: "United States of America" })).toBeVisible();
      await expect(page.getByRole("treeitem", { name: "Canada" })).toBeVisible();
    });

    await test.step("navigate using tree", async () => {
      await page
        .getByTestId("hierarchical-tree")
        .getByRole("link", { name: "United States of America" })
        .click();

      await expect(page.getByText("NameUnited States of America")).toBeVisible();
      await expect(page.getByText("Children5")).toBeVisible();
    });

    await test.step("navigate using tab", async () => {
      await page.getByText("Children5").click();
      await expect(page.getByRole("link", { name: "atl1" })).toBeVisible();
    });
  });

  test("should select a site using the Explore tab of relationship input", async ({ page }) => {
    await test.step("navigate to InfraDevice creation page", async () => {
      await page.goto("/objects/InfraDevice");
      await page.getByTestId("create-object-button").click();
    });

    await test.step("open site selection and verify All tab", async () => {
      await page.getByLabel("Site").click();
      await expect(page.getByRole("tab", { name: "All" })).toBeVisible();
      await expect(page.getByRole("option", { name: "atl1" })).toBeVisible();
    });

    await test.step("navigate through hierarchy in Explore tab", async () => {
      await page.getByRole("tab", { name: "Explore" }).click();
      await page.getByRole("option", { name: "North America Continent" }).click();
      await page.getByRole("option", { name: "United States of America" }).click();
      await page.getByRole("option", { name: "atl1 Site" }).click();
    });

    await test.step("verify selected site", async () => {
      await expect(page.getByLabel("Site")).toContainText("atl1");
    });
  });
});
