import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/ipam - Ipam home page", () => {
  test.describe.configure({ mode: "serial" });

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

    test("create, validate ui then delete a prefix with a parents and children", async ({
      page,
    }) => {
      await page.goto("/ipam");
      await expect(page.getByRole("treeitem", { name: "10.0.0.0/8" })).toBeVisible();

      await test.step("validate initial tree", async () => {
        await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(4);
      });

      await test.step("create a prefix at top level", async () => {
        await page.getByTestId("create-object-button").click();
        await page.getByLabel("Prefix *").fill("11.0.0.0/8");
        await page.getByRole("button", { name: "Save" }).click();
        await expect(page.getByText("IPPrefix created")).toBeVisible();
      });

      await test.step("validate new top level tree", async () => {
        await expect(page.getByRole("treeitem", { name: "11.0.0.0/8" })).toBeVisible();
        await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(5);
      });

      await test.step("create a children prefix", async () => {
        await page.getByTestId("create-object-button").click();
        await page.getByLabel("Prefix *").fill("11.0.0.0/16");
        await page.getByRole("button", { name: "Save" }).click();
        await expect(page.getByText("IPPrefix created")).toBeVisible();
      });

      await test.step("validate new top level tree", async () => {
        await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(5);
        await page
          .getByRole("treeitem", { name: "11.0.0.0/8" })
          .getByTestId("tree-item-toggle")
          .click();
        await expect(page.getByRole("treeitem", { name: "11.0.0.0/16" })).toBeVisible();
        await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(6);
      });

      await test.step("create a prefix between a parent and its children", async () => {
        await page.getByTestId("create-object-button").click();
        await page.getByLabel("Prefix *").fill("11.0.0.0/10");
        await page.getByRole("button", { name: "Save" }).click();
        await expect(page.getByText("IPPrefix created")).toBeVisible();
      });

      await test.step("validate tree position", async () => {
        await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(6);
        await page
          .getByRole("treeitem", { name: "11.0.0.0/10" })
          .getByTestId("tree-item-toggle")
          .click();
        await expect(page.getByRole("treeitem", { name: "11.0.0.0/16" })).toBeVisible();
        await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(7);
      });

      await test.step("delete a prefix between 2 other prefixes", async () => {
        await page.getByTestId("ipam-tree").getByRole("link", { name: "11.0.0.0/8" }).click();
        await page.getByText("Prefix Details").click();

        await page
          .getByRole("row", { name: "11.0.0.0/10" })
          .getByTestId("delete-row-button")
          .click();
        await expect(page.getByTestId("modal-delete")).toContainText(
          "Are you sure you want to delete the Prefix: 11.0.0.0/10"
        );
        await page.getByTestId("modal-delete-confirm").click();

        await expect(page.getByText("Prefix 11.0.0.0/10 deleted")).toBeVisible();
      });

      await test.step("validate deleted prefix is removed from tree", async () => {
        await expect(page.getByRole("treeitem", { name: "11.0.0.0/10" })).toBeHidden();
        await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(6);
      });

      await test.step("delete a children prefix", async () => {
        await page
          .getByRole("row", { name: "11.0.0.0/16" })
          .getByTestId("delete-row-button")
          .click();
        await expect(page.getByTestId("modal-delete")).toContainText(
          "Are you sure you want to delete the Prefix: 11.0.0.0/16"
        );
        await page.getByTestId("modal-delete-confirm").click();

        await expect(page.getByText("Prefix 11.0.0.0/16 deleted")).toBeVisible();
      });

      await test.step("validate deleted prefix is removed from tree", async () => {
        await expect(page.getByRole("treeitem", { name: "11.0.0.0/16" })).toBeHidden();
        await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(5);
      });

      await test.step("delete top level prefix", async () => {
        await page.getByText("Summary").click();
        await page.getByRole("link", { name: "All Prefixes" }).click();
        // Set pagination limit to 50 to display the prefix to delete
        await page
          .getByTestId("ipam-main-content")
          .getByTestId("select-open-option-button")
          .click();
        await page.getByText("50").click();
        await page
          .getByRole("row", { name: "11.0.0.0/8" })
          .getByTestId("delete-row-button")
          .click();
        await expect(page.getByTestId("modal-delete")).toContainText(
          "Are you sure you want to delete the Prefix: 11.0.0.0/8"
        );
        await page.getByTestId("modal-delete-confirm").click();

        await expect(page.getByText("Prefix 11.0.0.0/8 deleted")).toBeVisible();
      });

      await test.step("validate deleted prefix is removed from tree", async () => {
        await expect(page.getByRole("treeitem", { name: "11.0.0.0/8" })).toBeHidden();
        await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(4);
      });
    });

    test("create, validate ui then delete an ip address", async ({ page }) => {
      await page.goto("/ipam/addresses?ipam-tab=ip-details");

      await test.step("create an ip address", async () => {
        await page.getByTestId("create-object-button").click();
        await page.getByLabel("Address *").fill("10.0.0.1/16");
        await page.getByRole("button", { name: "Save" }).click();
        await expect(page.getByText("IPAddress created")).toBeVisible();
      });

      await test.step("Verify ip address is visible under its prefix", async () => {
        await page
          .getByRole("treeitem", { name: "10.0.0.0/8" })
          .getByTestId("tree-item-toggle")
          .click();
        await page.getByRole("link", { name: "10.0.0.0/16" }).click();
        await expect(page.getByRole("treeitem", { name: "10.0.0.0/16" })).toBeVisible();
        await expect(page.getByRole("row", { name: "10.0.0.1/16" })).toBeVisible();
      });

      await test.step("update ip address from list", async () => {
        await page
          .getByRole("row", { name: "10.0.0.1/16" })
          .getByTestId("update-row-button")
          .click();
        await page.getByLabel("Description").fill("test");
        await page.getByRole("button", { name: "Save" }).click();
        await expect(page.getByText("IPAddress updated")).toBeVisible();
        await expect(page.getByRole("row", { name: "10.0.0.1/16" })).toContainText("test");
      });

      await test.step("update ip address from summary", async () => {
        await page
          .getByRole("row", { name: "10.0.0.1/16" })
          .getByRole("link", { name: "10.0.0.1/16" })
          .click();

        await page.getByTestId("edit-button").click();
        await page.getByLabel("Description").fill("from summary");
        await page.getByRole("button", { name: "Save" }).click();
        await expect(page.getByText("IPAddress updated")).toBeVisible();
        await expect(page.getByText("Descriptionfrom summary")).toBeVisible();
      });

      await test.step("delete ip address", async () => {
        await page.getByRole("link", { name: "All IP Addresses" }).click();

        await page
          .getByRole("row", { name: "10.0.0.1/16 from summary" })
          .getByTestId("delete-row-button")
          .click();
        await expect(page.getByTestId("modal-delete")).toContainText(
          "Are you sure you want to delete the IP address: 10.0.0.1/16"
        );
        await page.getByTestId("modal-delete-confirm").click();

        await expect(page.getByText("Address 10.0.0.1/16 deleted")).toBeVisible();
        await expect(page.getByRole("row", { name: "10.0.0.1/16" })).toBeHidden();
      });
    });
  });
});
