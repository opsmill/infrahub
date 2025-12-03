import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("/ipam - IP Namespace", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("ip-namespace");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("access ip namespace list page", async ({ page }) => {
    await page.goto(`/ipam?branch=${BRANCH_NAME}`);
    await page.getByTestId("namespace-select").click();
    await page.getByRole("link", { name: "View all IP namespaces" }).click();
    await expect(page.getByRole("link", { name: "default" })).toBeVisible();
    expect(page.url()).toContain(`/ipam/namespaces?branch=${BRANCH_NAME}`);
  });

  test("create ip namespace", async ({ page }) => {
    await page.goto(`/ipam/namespaces?branch=${BRANCH_NAME}`);

    await expect(page.getByRole("link", { name: "default" })).toBeVisible();

    await page.getByTestId("create-object-button").click();
    await page.getByLabel("Name *").fill("test-namespace");
    await page.getByRole("button", { name: "Save" }).click();

    await expect(page.getByText("Namespace created")).toBeVisible();
    await expect(page.getByRole("link", { name: "test-namespace" })).toBeVisible();
  });

  test("switch from default ip namespace", async ({ page }) => {
    await page.goto(`/ipam?branch=${BRANCH_NAME}`);

    await expect(page.getByTestId("namespace-select")).toContainText("default");

    await page.getByTestId("namespace-select").click();
    await page.getByRole("option", { name: "test-namespace" }).click();

    await expect(page.getByTestId("namespace-select")).toContainText("test-namespace");
    expect(page.url()).toContain("namespace=");
  });

  test("search ip namespace in list page", async ({ page }) => {
    await page.goto(`/ipam/namespaces?branch=${BRANCH_NAME}`);

    await expect(page.getByRole("link", { name: "default" })).toBeVisible();
    await expect(page.getByRole("link", { name: "test-namespace" })).toBeVisible();

    await page.getByPlaceholder("Search IP Namespace").fill("test");
    await expect(page.getByRole("link", { name: "default" })).not.toBeVisible();
    await expect(page.getByRole("link", { name: "test-namespace" })).toBeVisible();

    await page.getByPlaceholder("Search IP Namespace").fill("def");
    await expect(page.getByRole("link", { name: "default" })).toBeVisible();
    await expect(page.getByRole("link", { name: "test-namespace" })).not.toBeVisible();

    await page.getByPlaceholder("Search IP Namespace").fill("xyz");
    await expect(page.getByRole("link", { name: "default" })).not.toBeVisible();
    await expect(page.getByRole("link", { name: "test-namespace" })).not.toBeVisible();
    await expect(page.getByText("No IP Namespace found")).toBeVisible();
  });

  test("redirects to IP Prefixes view when switching namespace if user is viewing an ip prefix", async ({
    page,
  }) => {
    await page.goto(`/ipam?branch=${BRANCH_NAME}`);
    await page.getByRole("link", { name: "10.0.0.0/16" }).click();
    await expect(page.getByRole("heading", { name: "10.0.0.0/16" })).toBeVisible();

    await page.getByTestId("namespace-select").click();
    await page.getByRole("option", { name: "test-namespace" }).click();

    await expect(page.getByText("No IP Prefix found")).toBeVisible();
    expect(page.url()).toContain("namespace=");
  });

  test("redirects to IP Addresses view when switching namespace if user is viewing an ip address", async ({
    page,
  }) => {
    await page.goto(`/ipam/ip_addresses?branch=${BRANCH_NAME}`);
    await page.getByRole("link", { name: "10.0.0.1/32" }).click();

    await page.getByTestId("namespace-select").click();
    await page.getByRole("option", { name: "test-namespace" }).click();

    await expect(page.getByText("No IP Address found")).toBeVisible();
    expect(page.url()).toContain("namespace=");
    expect(page.url()).toContain("/ipam/ip_addresses");
  });

  test("shows error when ip namespace does not exist", async ({ page }) => {
    await page.goto(`/ipam?namespace=non-existent&branch=${BRANCH_NAME}`);
    await expect(page.getByText("IP Namespace non-existent not found.")).toBeVisible();

    await page.getByRole("link", { name: "Go to default IP namespace" }).click();
    await expect(page.getByTestId("namespace-select")).toContainText("default");
  });

  test("create, validate ui and delete a prefix on other namespace", async ({ page }) => {
    await page.goto(`/ipam?branch=${BRANCH_NAME}`);
    await page.getByTestId("namespace-select").click();
    await page.getByRole("option", { name: "test-namespace" }).click();
    const ipamTree = page.getByRole("treegrid", { name: "IPAM tree" });

    await test.step("create a prefix at top level", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Prefix *").fill("11.0.0.0/8");
      await page.getByText("IP Namespace Kind").getByLabel("IPAM Namespace").click();
      await page.getByRole("option", { name: "test-namespace" }).click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("IP Prefix 11.0.0.0/8 created")).toBeVisible();
    });

    await test.step("validate new top level tree", async () => {
      await expect(ipamTree.getByText("11.0.0.0/8")).toBeVisible();
      expect(await ipamTree.getByRole("row").count()).toEqual(1);
    });

    await test.step("create a children prefix", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Prefix *").fill("11.0.0.0/16");
      await page.getByText("IP Namespace Kind").getByLabel("IPAM Namespace").click();
      await page.getByRole("option", { name: "test-namespace" }).click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("IP Prefix 11.0.0.0/16 created")).toBeVisible();
    });

    await test.step("validate new top level tree", async () => {
      expect(await ipamTree.getByRole("row").count()).toEqual(1);
      await ipamTree.getByRole("button", { name: "Expand 11.0.0.0/8" }).click();
      await expect(ipamTree.getByText("11.0.0.0/16")).toBeVisible();
      expect(await ipamTree.getByRole("row").count()).toEqual(2);
    });

    await test.step("create a prefix between a parent and its children", async () => {
      await ipamTree.getByText("11.0.0.0/8").click();

      // validate breadcrumb
      const breadcrumb = page.getByTestId("breadcrumb-navigation");
      await expect(breadcrumb.getByRole("link", { name: "11.0.0.0/8" })).toBeVisible();
      await breadcrumb.getByRole("button", { name: "Select a different IP Prefix" }).click();
      await expect(page.getByRole("option")).toHaveCount(2);
      await page.getByPlaceholder("Search...").press("Escape");

      await page.getByRole("link", { name: "Children" }).click();
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Prefix *").fill("11.0.0.0/10");
      await page.getByText("IP Namespace Kind").getByLabel("IPAM Namespace").click();
      await page.getByRole("option", { name: "test-namespace" }).click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("IP Prefix 11.0.0.0/10 created")).toBeVisible();
    });

    await test.step("validate tree position", async () => {
      expect(await ipamTree.getByRole("row").count()).toEqual(2);
      await ipamTree.getByRole("button", { name: "Expand 11.0.0.0/10" }).click();
      await expect(ipamTree.getByText("11.0.0.0/16")).toBeVisible();
      expect(await ipamTree.getByRole("row").count()).toEqual(3);
    });

    await test.step("delete a prefix between 2 other prefixes", async () => {
      await ipamTree.getByText("11.0.0.0/10").click();

      // validate breadcrumb
      const breadcrumb = page.getByTestId("breadcrumb-navigation");
      await expect(breadcrumb.getByRole("link", { name: "11.0.0.0/10" })).toBeVisible();
      await breadcrumb.getByRole("button", { name: "Select a different IP Prefix" }).last().click();
      await expect(page.getByRole("option")).toHaveCount(1);
      await page.getByPlaceholder("Search...").press("Escape");

      await page.getByTestId("object-details-menu").click();
      await page.getByRole("menuitem", { name: "Delete" }).click();
      await expect(page.getByTestId("modal-delete")).toContainText(
        'Are you sure you want to remove the IP Prefix"11.0.0.0/10"?'
      );
      await page.getByTestId("modal-delete-confirm").click();

      await expect(page.getByText("Object 11.0.0.0/10 deleted")).toBeVisible();
    });

    await test.step("validate deleted prefix is removed from tree", async () => {
      await expect(ipamTree.getByText("11.0.0.0/8")).toBeVisible();
      await expect(ipamTree.getByText("11.0.0.0/16")).toBeVisible();
      await expect(ipamTree.getByText("11.0.0.0/10")).toBeHidden();
      expect(await ipamTree.getByRole("row").count()).toEqual(2);
    });

    await test.step("delete a children prefix", async () => {
      await page.getByRole("link", { name: "Children" }).click();
      await page.getByTestId("actions-cell-11.0.0.0/16").click();
      await page.getByRole("menuitem", { name: "Delete" }).click();
      await expect(page.getByTestId("modal-delete")).toContainText(
        "Are you sure you want to remove 11.0.0.0/16?"
      );
      await page.getByTestId("modal-delete-confirm").click();
      await expect(page.getByText("Object 11.0.0.0/16 deleted")).toBeVisible();
    });

    await test.step("validate deleted prefix is removed from tree", async () => {
      await expect(ipamTree.getByText("11.0.0.0/16")).toBeHidden();
      expect(await ipamTree.getByRole("row").count()).toEqual(1);
    });

    await test.step("delete top level prefix", async () => {
      await page.getByTestId("object-details-menu").click();
      await page.getByRole("menuitem", { name: "Delete" }).click();
      await expect(page.getByTestId("modal-delete")).toContainText(
        'Are you sure you want to remove the IP Prefix"11.0.0.0/8"?'
      );
      await page.getByTestId("modal-delete-confirm").click();
      await expect(page.getByText("Object 11.0.0.0/8 deleted")).toBeVisible();
    });

    await test.step("validate deleted prefix is removed from tree", async () => {
      await expect(ipamTree.getByText("11.0.0.0/8")).toBeHidden();
      await expect(ipamTree.getByText("No ip prefix", { exact: true })).toBeVisible();
    });
  });

  test("delete ip namespace", async ({ page }) => {
    await page.goto(`/ipam/namespaces?branch=${BRANCH_NAME}`);

    await page.getByRole("link", { name: "test-namespace" }).click();
    await page.getByTestId("delete-button").click();
    await expect(page.getByTestId("modal-delete")).toContainText(
      'Are you sure you want to remove the IPAM Namespace"test-namespace"?'
    );
    await page.getByTestId("modal-delete-confirm").click();
    await expect(page.getByText("Object test-namespace deleted")).toBeVisible();

    await expect(page.getByRole("link", { name: "test-namespace" })).toBeHidden();
  });
});
