import { expect, test as setup } from "@playwright/test";
import {
  ACCOUNT_STATE_PATH,
  ADMIN_CREDENTIALS,
  READ_ONLY_CREDENTIALS,
  READ_WRITE_CREDENTIALS,
} from "../tests/utils";

setup("authenticate admin", async ({ page }) => {
  await page.goto("/signin");
  await expect(page.getByText("Sign in to your account")).toBeVisible();
  await page.getByLabel("Username").fill(ADMIN_CREDENTIALS.username);
  await page.getByLabel("Password").fill(ADMIN_CREDENTIALS.password);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByTestId("current-user-avatar-button")).toBeVisible();
  await page.context().storageState({ path: ACCOUNT_STATE_PATH.ADMIN });
});

setup("authenticate read-write", async ({ page }) => {
  await page.goto("/signin");
  await expect(page.getByText("Sign in to your account")).toBeVisible();
  await page.getByLabel("Username").fill(READ_WRITE_CREDENTIALS.username);
  await page.getByLabel("Password").fill(READ_WRITE_CREDENTIALS.password);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByTestId("current-user-avatar-button")).toBeVisible();
  await page.context().storageState({ path: ACCOUNT_STATE_PATH.READ_WRITE });
});

setup("authenticate read-only", async ({ page }) => {
  await page.goto("/signin");
  await expect(page.getByText("Sign in to your account")).toBeVisible();
  await page.getByLabel("Username").fill(READ_ONLY_CREDENTIALS.username);
  await page.getByLabel("Password").fill(READ_ONLY_CREDENTIALS.password);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByTestId("current-user-avatar-button")).toBeVisible();
  await page.context().storageState({ path: ACCOUNT_STATE_PATH.READ_ONLY });
});
