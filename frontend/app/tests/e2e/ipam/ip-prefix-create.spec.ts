import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("/ipam - Allocate an ip prefix with pool", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("ip-prefix-create");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should create an IP prefix at IPAM root, allocate a child prefix, and allocate IP addresses from the pool", async ({
    page,
  }) => {
    await test.step("Navigate to IPAM root and open create prefix form", async () => {
      await page.goto(`ipam?branch=${BRANCH_NAME}`);
      await page.getByTestId("create-object-button").click();
    });

    await test.step("Create a root IP prefix 11.0.0.0/8 manually", async () => {
      await page.getByLabel("Prefix *").fill("11.0.0.0/8");
      await page.getByLabel("Member Type").click();
      await page.getByRole("option", { name: "Prefix Prefix serves as" }).click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("IP Prefix 11.0.0.0/8 created")).toBeVisible();
    });

    await test.step("Allocate the available child prefix 11.0.0.0/9 from the root prefix", async () => {
      await page.getByTestId("identifier-cell").getByRole("link", { name: "11.0.0.0/8" }).click();
      await page
        .getByTestId("ip-prefix-available")
        .getByRole("button", { name: "11.0.0.0/9" })
        .click();
      await expect(page.getByLabel("Prefix *")).toHaveValue("11.0.0.0/9");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("IP Prefix 11.0.0.0/9 created")).toBeVisible();
    });

    await test.step("Verify child prefix 11.0.0.0/9 details and available ip addresses", async () => {
      await page.getByTestId("identifier-cell").getByRole("link", { name: "11.0.0.0/9" }).click();
      await expect(
        page
          .getByTestId("ip-address-available")
          .getByRole("button", { name: "11.0.0.1/9 11.127.255.254/9" })
      ).toBeVisible();
      await expect(page.getByText("More than 65536 IP addresses")).toBeVisible();
    });

    await test.step("Allocate the first IP address (11.0.0.1/9) from the table", async () => {
      await page
        .getByTestId("ip-address-available")
        .getByRole("button", { name: "11.0.0.1/9 11.127.255.254/9" })
        .click();
      await expect(page.getByLabel("Address *")).toHaveValue("11.0.0.1/9");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("IP Address 11.0.0.1/9 created")).toBeVisible();
      await expect(
        page.getByTestId("identifier-cell").getByRole("link", { name: "11.0.0.1/9" })
      ).toBeVisible();
      await expect(
        page.getByTestId("ip-address-available").getByRole("button", { name: "11.0.0.2/9" })
      ).toBeVisible();
    });

    await test.step("Creation form should suggest an available IP address within parent prefix", async () => {
      await page.getByTestId("create-object-button").click();
      await expect(page.getByLabel("Address *")).toHaveValue("11.0.0.2/9");
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("IP Address 11.0.0.2/9 created")).toBeVisible();
    });
  });
});
