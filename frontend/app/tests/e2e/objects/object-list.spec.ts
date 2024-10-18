import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/objects/:objectKind", () => {
  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test.describe("when not logged in", () => {
    test.skip("should not be able to create a new object", async ({ page }) => {
      await page.goto("/objects/BuiltinTag");

      await expect(page.getByRole("heading", { name: "Tag" })).toBeVisible();
      await expect(
        page.getByText("Standard Tag object to attached to other objects to provide some context.")
      ).toBeVisible();
      await expect(page.getByTestId("create-object-button")).toBeDisabled();
      await expect(page.getByRole("row", { name: "blue" }).getByRole("button")).toBeDisabled();
    });

    test.skip("should be able to open object details in a new tab", async ({ page, context }) => {
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
      await expect(page.locator("thead")).toContainText("Kind");
    });

    test("should display default column when a relationship schema has no attributes/relationship", async ({
      page,
    }) => {
      await page.goto("/objects/CoreStandardGroup");
      await page.getByTestId("object-items").getByRole("link", { name: "arista_devices" }).click();
      await page.getByText("Members").click();
      await expect(page.getByRole("columnheader", { name: "Type" })).toBeVisible();
      await expect(page.getByRole("columnheader", { name: "Name" })).toBeVisible();
    });

    test("clicking on a relationship value redirects to its details page", async ({ page }) => {
      await page.goto("/objects/InfraDevice");
      await page.getByRole("link", { name: "Juniper JunOS" }).first().click();
      await expect(page.getByText("NameJuniper JunOS")).toBeVisible();
      expect(page.url()).toContain("/objects/InfraPlatform/");
    });

    test("should be able to create a new object", async ({ page }) => {
      await page.goto("/objects/BuiltinTag");

      await expect(page.getByRole("heading", { name: "Tag" })).toBeVisible();
      await expect(page.getByTestId("create-object-button")).toBeEnabled();
      await expect(page.getByRole("row", { name: "blue" }).getByRole("button")).toBeEnabled();
      await page.getByTestId("create-object-button").click();
      await expect(page.getByRole("heading", { name: "Create Tag", exact: true })).toBeVisible();
    });
  });
});
