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
      await expect(page.getByRole("link", { name: "LocationContinent" }).first()).toBeVisible();
      await expect(page.getByRole("link", { name: "LocationCountry" }).first()).toBeVisible();
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
      await expect(page.getByRole("link", { name: "Atlanta" })).toBeVisible();
    });
  });
});
