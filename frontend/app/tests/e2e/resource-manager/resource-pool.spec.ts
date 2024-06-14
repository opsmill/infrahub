import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe.only("/resource-manager - Resource Manager", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("create a new pool", async ({ page }) => {
    await Promise.all([
      page.waitForResponse((response) => {
        const reqData = response.request().postDataJSON();
        const status = response.status();

        return reqData?.operationName === "CoreResourcePool" && status === 200;
      }),

      page.goto("/resource-manager"),
    ]);
    await page.getByTestId("create-object-button").click();

    await page.getByLabel("Select an object type").click();

    await Promise.all([
      page.waitForResponse((response) => {
        const reqData = response.request().postDataJSON();
        const status = response.status();

        return reqData?.operationName === "ProfileCoreIPPrefixPool" && status === 200;
      }),

      page.getByRole("option", { name: "CoreIPPrefixPool" }).click(),
    ]);

    await page.getByLabel("Name *").fill("test prefix pool");
    await page.getByLabel("Resources *").click();
    await page.getByRole("option", { name: "10.0.0.0/8" }).click();
    await page.getByRole("option", { name: "10.0.0.0/16" }).click();
    await page.getByRole("option", { name: "10.1.0.0/16" }).click();
    await page.getByLabel("Resources *").click();
    await page.getByTestId("select2step-1").getByTestId("select-open-option-button").click();
    await page.getByRole("option", { name: "Namespace" }).click();
    await page.getByTestId("select2step-2").getByTestId("select-open-option-button").click();
    await page.getByRole("option", { name: "default" }).click();
    await page.getByRole("button", { name: "Save" }).click();

    await expect(page.getByText("PrefixPool created")).toBeVisible();
    await expect(page.getByRole("link", { name: "test prefix pool" })).toBeVisible();
  });

  test("see details and edit a pool", async ({ page }) => {
    await page.goto("/resource-manager");
    await page.getByRole("link", { name: "test prefix pool" }).click();

    await expect(page.getByText("Core IP Prefix Pool")).toBeVisible();
    await expect(page.getByText("Nametest prefix pool")).toBeVisible();
    await expect(page.getByText("Description-")).toBeVisible();
    expect(page.url()).toContain("/resource-manager/");

    await page.getByTestId("edit-button").click();
    await page.getByLabel("Description").fill("a test pool for e2e");
    await page.getByRole("button", { name: "Save" }).click();

    await expect(page.getByText("PrefixPool updated")).toBeVisible();
    await expect(page.getByText("Descriptiona test pool for e2e")).toBeVisible();
  });

  test("delete a pool", async ({ page }) => {
    await page.goto("/resource-manager");

    await page
      .getByRole("row", { name: "test prefix pool" })
      .getByTestId("delete-row-button")
      .click();
    await page.getByTestId("modal-delete-confirm").click();

    await expect(page.getByText("Object test prefix pool")).toBeVisible();
    await expect(page.getByRole("link", { name: "test prefix pool" })).toBeHidden();
  });
});
