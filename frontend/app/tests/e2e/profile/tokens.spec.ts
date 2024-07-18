import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/profile?tab=tokens", () => {
  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test.describe("when not logged in as admin account", () => {
    test("should not access profile tokens", async ({ page }) => {
      await page.goto("/");
      await expect(page.getByText("Just a moment")).not.toBeVisible();
      await page.goto("/profile?tab=tokens");
      await expect(page.getByText("This operation requires")).toBeVisible();
    });
  });

  test.describe("when logged in as admin account", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should access and manage profile tokens", async ({ page }) => {
      await test.step("go to profile page and access tokens", async () => {
        await page.goto("/");
        await page.getByTestId("current-user-avatar-button").click();
        await page.getByRole("menuitem", { name: "Your Profile" }).click();
        await page.getByText("Tokens").click();
        await expect(page.getByRole("heading", { name: "Tokens" })).toBeVisible();
        await expect(page.getByTestId("create-object-button")).toBeVisible();
      });

      await test.step("create a new token", async () => {
        await page.getByTestId("create-object-button").click();
        await expect(page.getByRole("button", { name: "Save" })).toBeVisible();
        await page.getByLabel("Name *").fill("test token");
        await page.getByLabel("Expiration *").click();
        await page.getByLabel("Expiration *").click();
        await page.getByLabel("Choose Sunday, July 21st,").click();
        await page.getByRole("button", { name: "Save" }).click();
        await expect(page.getByRole("heading", { name: "Token created succesfuly" })).toBeVisible();
        await expect(page.getByRole("button", { name: "Confirm" })).toBeVisible();
        await page.getByRole("button", { name: "Confirm" }).click();
        await expect(page.getByRole("button", { name: "Confirm" })).not.toBeVisible();
      });

      await test.step("verify the new token", async () => {
        await expect(page.getByText("test token")).toBeVisible();
        await page.getByText("-07-21T00:00:00+02:00").click();
      });

      await test.step("delete the new token", async () => {
        await page
          .getByRole("row", { name: "test token 2024-07-21T00:00:00+02:00" })
          .getByTestId("delete-row-button")
          .click();
        await expect(page.getByText("Are you sure you want to")).toBeVisible();
        await page.getByTestId("modal-delete-confirm").click();
        await expect(page.getByText("Are you sure you want to")).not.toBeVisible();
        await expect(page.getByText("test token")).not.toBeVisible();
      });
    });
  });
});
