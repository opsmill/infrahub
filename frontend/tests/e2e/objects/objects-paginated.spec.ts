import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/objects/:objectname", () => {
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

    test("should filter the table", async ({ page }) => {
      await page.goto("/objects/BuiltinTag");
      const tagsNumber = await page.getByRole("row").count();

      // filter red
      await page.getByLabel("Filters").locator("svg").click();
      await page.getByLabel("name__value *").fill("red");
      await page.getByRole("button", { name: "Filter" }).click();
      await expect(page.getByText("name__value: red")).toBeVisible();
      await expect(page.getByRole("row")).toHaveCount(2);
      await expect(page.getByRole("cell", { name: "red" })).toBeVisible();

      // add 2nd filter
      await page.getByLabel("ids *").fill("no-id");
      await page.getByRole("button", { name: "Filter" }).click();
      await expect(page.getByText("ids: no-id")).toBeVisible();
      await expect(page.getByRole("row")).toHaveCount(1);
      await expect(page.getByText("No items found.")).toBeVisible();

      // remove 1 filter
      await page.getByText("ids: no-id").click();
      await expect(page.getByText("ids: no-id")).toBeHidden();
      await expect(page.getByRole("row")).toHaveCount(2);
      await expect(page.getByRole("cell", { name: "red" })).toBeVisible();

      // clear all
      await page.getByRole("button", { name: "Clear all" }).click();
      await expect(page.getByRole("row")).toHaveCount(tagsNumber);
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
