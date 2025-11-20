import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("/ipam - Allocate an ip address with pool", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("ip-address-pool");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("create an ip address using a pool", async ({ page }) => {
    await page.goto(`ipam/ip_addresses?branch=${BRANCH_NAME}`);
    await page.getByTestId("create-object-button").click();

    await page.getByTestId("select-open-pool-option-button").click();
    await page.getByRole("option", { name: "Management addresses pool" }).click();
    await expect(page.getByLabel("Address *")).toContainText("Allocated by pool");
    await expect(page.getByTestId("source-pool-badge")).toContainText("Management addresses pool");
    await page.getByLabel("Description").fill("address from pool");
    await page.getByRole("button", { name: "Save" }).click();

    await expect(page.getByText("IP Address 172.16.0.31/16 created")).toBeVisible();
    await page
      .getByTestId("object-list-search-bar")
      .getByRole("searchbox", { name: "Search" })
      .fill("172.16.0.31/16");
    await expect(page.getByText("address from pool")).toBeVisible();
  });
});
