import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/ipam - Ipam home page", () => {
  test.describe("When not logged in", () => {
    test("disable buttons that open creation form", async ({ page }) => {
      await page.goto("/ipam");

      await expect(page.getByTestId("create-object-button")).toBeDisabled();

      await page.getByText("Prefix Details").click();
      await expect(page.getByTestId("create-object-button")).toBeDisabled();

      await page.getByText("IP Details").click();
      await expect(page.getByTestId("create-object-button")).toBeDisabled();
    });
  });

  test("should load all ipam home page elements", async ({ page }) => {
    await page.goto("/ipam");

    await expect(page.getByText("IP Address Manager")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Navigation" })).toBeVisible();
    await expect(page.getByTestId("ipam-tree")).toBeVisible();
    await expect(page.getByTestId("ipam-main-content")).toBeVisible();
  });

  test.describe("CRUD", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("create, validate ui then delete a prefix", async ({ page }) => {
      await page.goto("/ipam");

      await page.getByTestId("create-object-button").click();
      await page
        .getByTestId("side-panel-container")
        .getByTestId("select-open-option-button")
        .click();
      await page.getByRole("option", { name: "IpamIPPrefix" }).click();
      await page.getByLabel("Prefix *").fill("10.3.0.0/16");
      await page.getByRole("button", { name: "Create" }).click();

      await expect(page.locator("#alert-success-IPPrefix-created")).toContainText(
        "IPPrefix created"
      );
      await page
        .getByRole("treeitem", { name: "10.0.0.0/8" })
        .getByTestId("tree-item-toggle")
        .click();
      await expect(page.getByRole("treeitem", { name: "10.3.0.0/16" })).toBeVisible();

      await page.getByText("Prefix Details").click();
      await page.getByRole("row", { name: "10.3.0.0/16" }).getByTestId("delete-row-button").click();
      await expect(page.getByTestId("modal-delete")).toContainText(
        "Are you sure you want to delete the Prefix: 10.3.0.0/16"
      );
      await page.getByTestId("modal-delete-confirm").click();

      await expect(page.getByTestId("alert-prefix-deleted")).toContainText(
        "Prefix 10.3.0.0/16 deleted"
      );
      await expect(page.getByRole("row", { name: "10.3.0.0/16" })).toBeHidden();
    });
  });
});
