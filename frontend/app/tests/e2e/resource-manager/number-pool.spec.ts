import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/resource-manager - Resource Manager", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("create a new pool", async ({ page }) => {
    await page.goto("/resource-manager");
    await page.getByTestId("create-object-button").click();
    await page.getByLabel("Select an object type").click();
    await page.getByText("Number PoolCore").click();
    await expect(page.getByText("Name *")).toBeVisible();
    await page.getByLabel("Name *").fill("number pool test");
    await expect(page.getByText("number pool test")).toBeVisible();
    await page.getByLabel("Node *").click();
    await page.getByText("Interface L2", { exact: true }).click();
    await page.getByLabel("Attribute *").click();
    await page.getByRole("option", { name: "Speed" }).click();
    await page.getByLabel("Start range *").fill("1");
    await page.getByLabel("End range *").fill("10");
    await page.getByRole("button", { name: "Create" }).click();
    await expect(page.getByText("Number pool created")).toBeVisible();
  });

  test("verfy pool details", async ({ page }) => {
    await page.goto("/resource-manager");
    await page.getByTestId("object-items").getByRole("link", { name: "number pool test" }).click();
    await expect(page.getByRole("cell", { name: "number pool test" }).first()).toBeVisible();
    await expect(page.getByText("Speed")).toBeVisible();
    await expect(page.getByText("1")).toBeVisible();
    await expect(page.getByText("10")).toBeVisible();
  });
});
