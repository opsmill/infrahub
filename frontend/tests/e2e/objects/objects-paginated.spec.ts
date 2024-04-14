import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/objects/:objectname", () => {
  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("should display 'kind' column on when the object is a generic", async ({ page }) => {
    await page.goto("/objects/CoreGroup");
    await expect(page.locator("thead")).toContainText("Kind");
  });

  test("should display default column when a relationship schema has no attributes/relationship", async ({
    page,
  }) => {
    await page.goto("/objects/CoreStandardGroup");
    await page.getByRole("link", { name: "arista_devices" }).click();
    await page.getByText("Members").click();
    await expect(page.getByRole("columnheader", { name: "Type" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Name" })).toBeVisible();
  });

  test.describe("when not logged in", () => {
    test("should not be able to create a new object", async ({ page }) => {
      await page.goto("/objects/BuiltinTag");

      await expect(page.getByRole("heading", { name: "Tag" })).toBeVisible();
      await expect(
        page.getByText("Standard Tag object to attached to other objects to provide some context.")
      ).toBeVisible();
      await expect(page.getByTestId("create-object-button")).toBeDisabled();
      await expect(page.getByRole("row", { name: "blue" }).getByRole("button")).toBeDisabled();
    });

    test("should be able to open object details in a new tab", async ({ page, context }) => {
      await page.goto("/objects/BuiltinTag");

      // When
      const objectDetailsLink = page.getByRole("link", { name: "blue" });
      const linkHref = await objectDetailsLink.getAttribute("href");
      await objectDetailsLink.click({ button: "middle" });

      // then
      const newTab = await context.waitForEvent("page");
      await newTab.waitForURL(linkHref);
      expect(newTab.url()).toContain(linkHref);
    });
  });

  test.describe("when logged in as Admin", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should be able to create a new object", async ({ page }) => {
      await page.goto("/objects/BuiltinTag");

      await expect(page.getByRole("heading", { name: "Tag" })).toBeVisible();
      await expect(page.getByTestId("create-object-button")).toBeEnabled();
      await expect(page.getByRole("row", { name: "blue" }).getByRole("button")).toBeEnabled();
      await page.getByTestId("create-object-button").click();
      await expect(page.getByRole("heading", { name: "Create Tag" })).toBeVisible();
    });
  });
});
