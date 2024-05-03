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

      await test.step("create a prefix", async () => {
        await page.getByTestId("create-object-button").click();
        await page
          .getByTestId("side-panel-container")
          .getByTestId("select-open-option-button")
          .click();
        await page.getByRole("option", { name: "IpamIPPrefix" }).click();
        await page.getByLabel("Prefix *").fill("2001:db8::600/120");
        await page.getByRole("button", { name: "Create" }).click();
        await expect(page.getByText("IPPrefix created")).toBeVisible();
      });

      await test.step("new prefix is correctly positioned in tree", async () => {
        await page
          .getByRole("treeitem", { name: "2001:db8::/112" })
          .getByTestId("tree-item-toggle")
          .click();
        await expect(page.getByRole("treeitem", { name: "2001:db8::600/120" })).toBeVisible();
      });

      await test.step("update a prefix from list", async () => {
        await page.getByText("Prefix Details").click();
        await page
          .getByRole("row", { name: "2001:db8::600/120" })
          .getByTestId("update-row-button")
          .click();
        await page.getByLabel("Description").fill("desc from list");
        await page.getByRole("button", { name: "Save" }).click();

        await expect(page.getByText("IPPrefix updated")).toBeVisible();
        await expect(page.getByRole("row", { name: "2001:db8::600/120" })).toContainText(
          "desc from list"
        );
      });

      await test.step("update a prefix from summary", async () => {
        await page
          .getByRole("row", { name: "2001:db8::600/120" })
          .getByRole("link", { name: "2001:db8::600/120" })
          .click();
        await page.getByText("Summary").click();

        await page.getByTestId("ip-summary-edit-button").click();
        await page.getByLabel("Description").fill("desc from summary");
        await page.getByRole("button", { name: "Save" }).click();
        await expect(page.getByText("IPPrefix updated")).toBeVisible();
        await expect(page.getByText("Descriptiondesc from summary")).toBeVisible();
      });

      await test.step("delete a prefix", async () => {
        await page.getByText("Prefix Details").click();
        await page
          .getByTestId("ipam-main-content")
          .getByRole("link", { name: "2001:db8::/112" })
          .click();

        await page
          .getByRole("row", { name: "2001:db8::600/120" })
          .getByTestId("delete-row-button")
          .click();
        await expect(page.getByTestId("modal-delete")).toContainText(
          "Are you sure you want to delete the Prefix: 2001:db8::600/120"
        );
        await page.getByTestId("modal-delete-confirm").click();

        await expect(page.getByTestId("alert-prefix-deleted")).toContainText(
          "Prefix 2001:db8::600/120 deleted"
        );
        await expect(page.getByRole("row", { name: "2001:db8::600/120" })).toBeHidden();
      });
    });

    test("create, validate ui then delete an ip address", async ({ page }) => {
      await page.goto("/ipam/addresses?ipam-tab=ip-details");

      await test.step("create an ip address", async () => {
        await page.getByTestId("create-object-button").click();
        await page
          .getByTestId("side-panel-container")
          .getByTestId("select-open-option-button")
          .click();
        await page.getByRole("option", { name: "IpamIPAddress" }).click();
        await page.getByLabel("Address *").fill("10.0.0.1/16");
        await page.getByRole("button", { name: "Create" }).click();
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

        await page.getByTestId("ip-summary-edit-button").click();
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
