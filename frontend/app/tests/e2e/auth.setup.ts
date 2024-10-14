import { expect, test as setup } from "@playwright/test";
import {
  ACCOUNT_STATE_PATH,
  ADMIN_CREDENTIALS,
  READ_ONLY_CREDENTIALS,
  READ_WRITE_CREDENTIALS,
} from "../constants";

setup("authenticate admin", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByText("Log in to your account")).toBeVisible();
  const loginButton = page.getByRole("button", {
    name: "Log in with your credentials",
  });
  if (await loginButton.isVisible()) {
    await loginButton.click();
  }
  await page.getByLabel("Username").fill(ADMIN_CREDENTIALS.username);
  await page.getByLabel("Password").fill(ADMIN_CREDENTIALS.password);
  await page.getByRole("button", { name: "Log in", exact: true }).click();

  await expect(page.getByTestId("authenticated-menu-trigger")).toBeVisible();
  await page.context().storageState({ path: ACCOUNT_STATE_PATH.ADMIN });
});

setup("authenticate read-write", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByText("Log in to your account")).toBeVisible();
  const loginButton = page.getByRole("button", {
    name: "Log in with your credentials",
  });
  if (await loginButton.isVisible()) {
    await loginButton.click();
  }
  await page.getByLabel("Username").fill(READ_WRITE_CREDENTIALS.username);
  await page.getByLabel("Password").fill(READ_WRITE_CREDENTIALS.password);
  await page.getByRole("button", { name: "Log in", exact: true }).click();

  await expect(page.getByTestId("authenticated-menu-trigger")).toBeVisible();
  await page.context().storageState({ path: ACCOUNT_STATE_PATH.READ_WRITE });
});

setup("authenticate read-only", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByText("Log in to your account")).toBeVisible();
  const loginButton = page.getByRole("button", {
    name: "Log in with your credentials",
  });
  if (await loginButton.isVisible()) {
    await loginButton.click();
  }
  await page.getByLabel("Username").fill(READ_ONLY_CREDENTIALS.username);
  await page.getByLabel("Password").fill(READ_ONLY_CREDENTIALS.password);
  await page.getByRole("button", { name: "Log in", exact: true }).click();

  await expect(page.getByTestId("authenticated-menu-trigger")).toBeVisible();
  await page.context().storageState({ path: ACCOUNT_STATE_PATH.READ_ONLY });
});
