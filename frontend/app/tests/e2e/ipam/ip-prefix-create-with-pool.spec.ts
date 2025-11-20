import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("/ipam - Allocate an ip prefix with pool", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("ip-prefix-pool");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("create an ip prefix using a pool", async ({ page }) => {
    await page.goto(`ipam?branch=${BRANCH_NAME}`);
    await page.getByTestId("create-object-button").click();

    await page.getByTestId("select-open-pool-option-button").click();
    await page.getByRole("option", { name: "External prefixes pool" }).click();
    await expect(page.getByLabel("Prefix *")).toContainText("Allocated by pool");
    await expect(page.getByTestId("source-pool-badge")).toContainText("External prefixes pool");
    await page.getByRole("textbox", { name: "Description" }).fill("prefix from pool");
    await page.getByRole("button", { name: "Save" }).click();

    await expect(page.getByText("IP Prefix 203.111.0.248/29 created")).toBeVisible();
    await page
      .getByTestId("object-list-search-bar")
      .getByRole("searchbox", { name: "Search" })
      .fill("203.111.0.248/29");
    await expect(page.getByText("prefix from pool")).toBeVisible();
  });
});
