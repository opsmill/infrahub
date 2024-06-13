import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/ipam - IP Namespace", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("create ip namespace", async ({ page }) => {
    await page.goto("/objects/BuiltinIPNamespace");

    await expect(page.getByRole("link", { name: "default", exact: true })).toBeVisible();

    await page.getByTestId("create-object-button").click();
    await page.getByLabel("Name *").fill("test-namespace");
    await page.getByRole("button", { name: "Save" }).click();

    await expect(page.getByText("Namespace created")).toBeVisible();
    await expect(page.getByRole("link", { name: "test-namespace" })).toBeVisible();
  });

  test("switch from default ip namespace", async ({ page }) => {
    await page.goto("/ipam");

    await expect(page.getByTestId("namespace-select").getByTestId("select-input")).toHaveValue(
      "default"
    );

    await page.getByTestId("namespace-select").getByTestId("select-open-option-button").click();
    await page.getByRole("option", { name: "test-namespace" }).click();

    await expect(page.getByTestId("namespace-select").getByTestId("select-input")).toHaveValue(
      "test-namespace"
    );
    expect(page.url()).toContain("namespace=");
    await expect(page.getByTestId("ipam-main-content")).toContainText("Showing 0 of 0 results");
  });

  test("redirects to IP Prefixes view when switching namespace if user is viewing an ip prefix", async ({
    page,
  }) => {
    await page.goto("/ipam/prefixes");
    await page.getByRole("link", { name: "10.0.0.0/16" }).click();

    await page.getByTestId("namespace-select").getByTestId("select-open-option-button").click();
    await page.getByRole("option", { name: "test-namespace" }).click();

    expect(page.url()).toContain("/ipam/prefixes?namespace=");
  });

  test("redirects to IP Addresses view when switching namespace if user is viewing an ip address", async ({
    page,
  }) => {
    await page.goto("/ipam/addresses?ipam-tab=ip-details");
    await page.getByRole("link", { name: "10.0.0.1/32" }).click();

    await page.getByTestId("namespace-select").getByTestId("select-open-option-button").click();
    await page.getByRole("option", { name: "test-namespace" }).click();

    expect(page.url()).toContain("/ipam/addresses?ipam-tab=ip-details&namespace=");
  });

  test("create, validate ui and delete a prefix on other namespace", async ({ page }) => {
    await Promise.all([
      page.waitForResponse((response) => {
        const reqData = response.request().postDataJSON();
        const status = response.status();

        return reqData?.operationName === "GET_TOP_LEVEL_PREFIXES" && status === 200;
      }),

      page.waitForResponse((response) => {
        const reqData = response.request().postDataJSON();
        const status = response.status();

        return reqData?.operationName === "GET_PREFIXES" && status === 200;
      }),

      page.goto("/ipam"),
    ]);
    await page.getByTestId("namespace-select").getByTestId("select-open-option-button").click();

    await Promise.all([
      page.waitForResponse((response) => {
        const reqData = response.request().postDataJSON();
        const status = response.status();

        return reqData?.operationName === "GET_TOP_LEVEL_PREFIXES" && status === 200;
      }),

      page.waitForResponse((response) => {
        const reqData = response.request().postDataJSON();
        const status = response.status();

        return reqData?.operationName === "GET_PREFIXES" && status === 200;
      }),

      page.getByRole("option", { name: "test-namespace" }).click(),
    ]);

    await test.step("create a prefix at top level", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Prefix *").fill("11.0.0.0/8");
      await page.getByTestId("select2step-1").getByTestId("select-open-option-button").click();

      await Promise.all([
        page.waitForResponse((response) => {
          const reqData = response.request().postDataJSON();
          const status = response.status();

          return reqData?.operationName === "DropdownOptions" && status === 200;
        }), // wait for second dropdown to appear

        page.getByRole("option", { name: "Namespace" }).click(),
      ]);

      await page.getByTestId("select2step-2").getByTestId("select-open-option-button").click();
      await page.getByRole("option", { name: "test-namespace" }).click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("IPPrefix created")).toBeVisible();
    });

    await test.step("validate new top level tree", async () => {
      await expect(page.getByRole("treeitem", { name: "11.0.0.0/8" })).toBeVisible();
      await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(1);
    });

    await test.step("create a children prefix", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Prefix *").fill("11.0.0.0/16");
      await page.getByTestId("select2step-1").getByTestId("select-open-option-button").click();

      await Promise.all([
        page.waitForResponse((response) => {
          const reqData = response.request().postDataJSON();
          const status = response.status();

          return reqData?.operationName === "DropdownOptions" && status === 200;
        }), // wait for second dropdown to appear

        page.getByRole("option", { name: "Namespace" }).click(),
      ]);

      await page.getByTestId("select2step-2").getByTestId("select-open-option-button").click();
      await page.getByRole("option", { name: "test-namespace" }).click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("IPPrefix created")).toBeVisible();
    });

    await test.step("validate new top level tree", async () => {
      await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(1);
      await page
        .getByRole("treeitem", { name: "11.0.0.0/8" })
        .getByTestId("tree-item-toggle")
        .click();
      await expect(page.getByRole("treeitem", { name: "11.0.0.0/16" })).toBeVisible();
      await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(2);
    });

    await test.step("create a prefix between a parent and its children", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Prefix *").fill("11.0.0.0/10");
      await page.getByTestId("select2step-1").getByTestId("select-open-option-button").click();

      await Promise.all([
        page.waitForResponse((response) => {
          const reqData = response.request().postDataJSON();
          const status = response.status();

          return reqData?.operationName === "DropdownOptions" && status === 200;
        }), // wait for second dropdown to appear

        page.getByRole("option", { name: "Namespace" }).click(),
      ]);

      await page.getByTestId("select2step-2").getByTestId("select-open-option-button").click();
      await page.getByRole("option", { name: "test-namespace" }).click();
      await page.getByRole("button", { name: "Save" }).click();
      await expect(page.getByText("IPPrefix created")).toBeVisible();
    });

    await test.step("validate tree position", async () => {
      await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(2);
      await page
        .getByRole("treeitem", { name: "11.0.0.0/10" })
        .getByTestId("tree-item-toggle")
        .click();
      await expect(page.getByRole("treeitem", { name: "11.0.0.0/16" })).toBeVisible();
      await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(3);
    });

    await test.step("delete a prefix between 2 other prefixes", async () => {
      await page.getByTestId("ipam-tree").getByRole("link", { name: "11.0.0.0/8" }).click();
      await page.getByText("Prefix Details").click();

      await page.getByRole("row", { name: "11.0.0.0/10" }).getByTestId("delete-row-button").click();
      await expect(page.getByTestId("modal-delete")).toContainText(
        "Are you sure you want to delete the Prefix: 11.0.0.0/10"
      );
      await page.getByTestId("modal-delete-confirm").click();

      await expect(page.getByText("Prefix 11.0.0.0/10 deleted")).toBeVisible();
    });

    await test.step("validate deleted prefix is removed from tree", async () => {
      await expect(page.getByRole("treeitem", { name: "11.0.0.0/10" })).toBeHidden();
      await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(2);
    });

    await test.step("delete a children prefix", async () => {
      await page.getByRole("row", { name: "11.0.0.0/16" }).getByTestId("delete-row-button").click();
      await expect(page.getByTestId("modal-delete")).toContainText(
        "Are you sure you want to delete the Prefix: 11.0.0.0/16"
      );
      await page.getByTestId("modal-delete-confirm").click();

      await expect(page.getByText("Prefix 11.0.0.0/16 deleted")).toBeVisible();
    });

    await test.step("validate deleted prefix is removed from tree", async () => {
      await expect(page.getByRole("treeitem", { name: "11.0.0.0/16" })).toBeHidden();
      await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(1);
    });

    await test.step("delete top level prefix", async () => {
      await page.getByText("Summary").click();
      await page.getByRole("link", { name: "All Prefixes" }).click();

      await page.getByRole("row", { name: "11.0.0.0/8" }).getByTestId("delete-row-button").click();
      await expect(page.getByTestId("modal-delete")).toContainText(
        "Are you sure you want to delete the Prefix: 11.0.0.0/8"
      );
      await page.getByTestId("modal-delete-confirm").click();

      await expect(page.getByText("Prefix 11.0.0.0/8 deleted")).toBeVisible();
    });

    await test.step("validate deleted prefix is removed from tree", async () => {
      await expect(page.getByRole("treeitem", { name: "11.0.0.0/8" })).toBeHidden();
      await expect(await page.getByTestId("ipam-tree-item").count()).toEqual(0);
    });
  });

  test("delete ip namespace", async ({ page }) => {
    await page.goto("/objects/BuiltinIPNamespace");

    await page
      .getByRole("row", { name: "test-namespace" })
      .getByTestId("delete-row-button")
      .click();
    await page.getByTestId("modal-delete-confirm").click();

    await expect(page.getByText("Object test-namespace deleted")).toBeVisible();
    await expect(page.getByRole("link", { name: "test-namespace" })).toBeHidden();
  });
});
