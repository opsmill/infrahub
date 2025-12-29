import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { saveScreenshotForDocs } from "../../utils";

test.describe("/profile?tab=tokens", () => {
  test.describe("when not logged in as admin account", () => {
    test("should not access profile tokens", async ({ page }) => {
      await page.goto("/profile?tab=tokens");
      await expect(page.getByText("Open Proposed changes", { exact: true })).toBeVisible();
    });
  });

  test.describe("when logged in as admin account", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should create and delete a account without expiration date", async ({ page }) => {
      await test.step("go to profile page and access tokens", async () => {
        await page.goto("/");
        await page.getByTestId("authenticated-menu-trigger").click();
        await page.getByRole("menuitem", { name: "Account settings" }).click();
        await page.getByText("Tokens").click();
        await expect(page.getByTestId("account-token-Created automatically")).toBeVisible();
        await page.getByRole("button", { name: "Add account token" }).click();
        await expect(page.getByRole("button", { name: "Save" })).toBeVisible();
        await saveScreenshotForDocs(page, "profile_tokens");
      });

      await test.step("create a new token", async () => {
        await page.getByLabel("Name *").fill("test token");
        await saveScreenshotForDocs(page, "profile_tokens_create");
        await page.getByRole("button", { name: "Save" }).click();
        await expect(page.getByText("For security reasons we cannot show it again.")).toBeVisible();
        await expect(page.getByRole("button", { name: "Confirm" })).toBeVisible();
        await saveScreenshotForDocs(page, "profile_tokens_copy");
        await page.getByRole("button", { name: "Confirm" }).click();
        await expect(page.getByRole("button", { name: "Confirm" })).not.toBeVisible();
      });

      const accountTokenCard = page.getByTestId("account-token-test token");

      await test.step("verify the new token", async () => {
        await expect(accountTokenCard).toContainText("test token");
        await expect(accountTokenCard).toContainText("This token has no expiration date");
      });

      await test.step("delete the new token", async () => {
        await accountTokenCard.getByRole("button", { name: "Delete token test token" }).click();
        await page.getByTestId("modal-delete-confirm").click();
        await expect(page.getByText("Are you sure you want to")).not.toBeVisible();
        await expect(accountTokenCard).not.toBeVisible();
      });
    });
  });
});
