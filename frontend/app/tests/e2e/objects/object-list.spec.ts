import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe.fixme("/objects/:objectKind", () => {
  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test.describe("when not logged in", () => {
    test("should not be able to create a new object", async ({ page }) => {
      await page.goto("/objects/BuiltinTag");

      await expect(page.getByRole("heading", { name: "Tag" })).toBeVisible();
      await expect(
        page.getByText("Standard Tag object to attach to other objects to provide some context.")
      ).toBeVisible();
      await expect(page.getByTestId("create-object-button")).toBeDisabled();
      await page.getByTestId("actions-cell-blue").click();
      await expect(page.getByRole("menuitem", { name: "Delete" })).toBeDisabled();
    });

    test("should be able to open object details in a new tab", async ({ page, context }) => {
      await page.goto("/objects/BuiltinTag");

      // When
      const objectDetailsLink = page.getByRole("link", { name: "blue" });
      const linkHref = await objectDetailsLink.getAttribute("href");
      const newTabPromise = context.waitForEvent("page");
      await objectDetailsLink.click({ button: "middle" });

      // then
      const newTab = await newTabPromise;
      await newTab.waitForURL(linkHref!);
      expect(newTab.url()).toContain(linkHref);
    });
  });

  test.describe("when logged in as Admin", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should display 'kind' column on when the object is a generic", async ({ page }) => {
      await page.goto("/objects/CoreGroup");
      await expect(page.getByTestId("object-items")).toContainText("Kind");
    });

    test("should display default column when a relationship schema has no attributes/relationships", async ({
      page,
    }) => {
      await page.goto("/objects/CoreStandardGroup");
      await page.getByTestId("object-items").getByRole("link", { name: "arista_devices" }).click();
      await page.getByText("Members").click();
      await expect(page.getByText("Node", { exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "Kind" })).toBeVisible();
    });

    test("clicking on a relationship value redirects to its details page", async ({ page }) => {
      await page.goto("/objects/InfraDevice");
      await page.getByRole("link", { name: "Juniper JunOS" }).first().click();
      await expect(page.getByText("NameJuniper JunOS", { exact: true })).toBeVisible();
      expect(page.url()).toContain("/objects/InfraPlatform/");
    });

    test("should be able to manage objects", async ({ page }) => {
      await page.goto("/objects/BuiltinTag");
      await expect(page.getByRole("heading", { name: "Tag" })).toBeVisible();
      await expect(page.getByTestId("create-object-button")).toBeEnabled();

      await test.step("create a new item from the list", async () => {
        await page.getByTestId("create-object-button").click();
        await page.getByLabel("Name *").fill("crud");
        await page.getByLabel("Description").fill("initial description");
        await page.getByRole("button", { name: "Save" }).click();

        await expect(page.getByRole("link", { name: "crud" })).toBeVisible();
        await expect(page.getByText("initial description")).toBeVisible();
      });

      await test.step("edit the item", async () => {
        await page.getByTestId("actions-cell-crud").click();
        await page.getByRole("menuitem", { name: "Edit" }).click();
        await page.getByLabel("Description").fill("description updated");
        await page.getByRole("button", { name: "Save" }).click();

        await expect(page.getByText("Tag updated")).toBeVisible();
        await expect(page.getByRole("link", { name: "crud" })).toBeVisible();
        await expect(page.getByText("description updated")).toBeVisible();
      });

      await test.step("delete the item", async () => {
        await page.getByTestId("actions-cell-crud").click();
        await page.getByRole("menuitem", { name: "Delete" }).click();
        await expect(page.getByTestId("modal-delete")).toBeVisible();
        await expect(page.getByText("Are you sure you want to remove crud")).toBeVisible();
        await page.getByTestId("modal-delete-confirm").click();
        await expect(page.getByText("Object crud deleted")).toBeVisible();
      });
    });
  });
});
