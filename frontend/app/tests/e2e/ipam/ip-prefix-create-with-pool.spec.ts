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

  test("create an ip prefix using a pool with a custom prefix length", async ({ page, request }) => {
    const branchName = generateRandomBranchName("ip-prefix-pool-prefixlen");
    await createBranchAPI(request, branchName);

    try {
      await page.goto(`ipam?branch=${branchName}`);
      await page.getByTestId("create-object-button").click();

      await page.getByTestId("select-open-pool-option-button").click();
      await page.getByRole("option", { name: "External prefixes pool" }).click();
      await expect(page.getByLabel("Prefix *")).toContainText("Allocated by pool");

      // The pool's default prefix length is surfaced as a placeholder.
      await expect(page.getByTestId("pool-prefix-length-input")).toHaveAttribute(
        "placeholder",
        "29"
      );

      // Override the pool's default prefix length with a smaller subnet size.
      await page.getByTestId("pool-prefix-length-input").fill("30");

      await page
        .getByRole("textbox", { name: "Description" })
        .fill("prefix from pool with custom size");
      await page.getByRole("button", { name: "Save" }).click();

      // The allocation honours the typed prefix length rather than the pool default.
      await expect(page.getByText(/IP Prefix 203\.111\.\d+\.\d+\/30 created/)).toBeVisible();
    } finally {
      await deleteBranchAPI(request, branchName);
    }
  });
});
