import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("Object filters", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("should filter the nodes list", async ({ page }) => {
    await test.step("access nodes list and verify initial state", async () => {
      await page.goto("/objects/InfraDevice");
      await expect(page.getByRole("heading", { name: "Device" })).toBeVisible();
      await expect(page.getByRole("link", { name: "atl1-core1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "den1-edge1" })).toBeVisible();
    });

    await test.step("filter using an attribute", async () => {
      await page.getByRole("button", { name: "Role" }).click();
      await page.getByLabel("Role").click();
      await page.getByRole("option", { name: "Edge Router" }).click();
      await page.getByRole("button", { name: "Filter", exact: true }).click();

      await expect(
        page.getByLabel("Active filters").getByLabel("Role contains edge")
      ).toBeVisible();
      await expect(page.getByRole("button", { name: "Clear filters" })).toBeVisible();

      await expect(page.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "den1-edge1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "atl1-core1" })).not.toBeVisible();
    });

    await test.step("filter using a relationship of cardinality one", async () => {
      await page.getByRole("button", { name: "Site" }).click();
      await page.getByLabel("Site").click();
      await page.getByRole("option", { name: "atl1" }).click();
      await page.getByRole("button", { name: "Filter", exact: true }).click();

      await expect(
        page.getByLabel("Active filters").getByLabel("Site contains atl1")
      ).toBeVisible();
      await expect(page.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "den1-edge1" })).not.toBeVisible();
      await expect(page.getByRole("link", { name: "atl1-core1" })).not.toBeVisible();
    });

    await test.step("remove an attribute filter", async () => {
      await page.getByLabel("Active filters").getByLabel("Role contains edge").click();

      await expect(page.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "atl1-core1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "den1-edge1" })).not.toBeVisible();
    });

    await test.step("filter using a relationship of cardinality many", async () => {
      await page.getByRole("button", { name: "Tags" }).click();
      await page.getByLabel("Tags").click();
      await page.getByRole("option", { name: "blue" }).click();
      await page.getByLabel("Tags").click();
      await page.getByRole("button", { name: "Filter", exact: true }).click();

      await expect(
        page.getByLabel("Active filters").getByLabel("Site contains atl1")
      ).toBeVisible();
      await expect(
        page.getByLabel("Active filters").getByLabel("Tags contains blue")
      ).toBeVisible();

      await expect(page.getByRole("link", { name: "atl1-core1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "atl1-edge1" })).not.toBeVisible();
      await expect(page.getByRole("link", { name: "den1-edge1" })).not.toBeVisible();
    });

    await test.step("clear all filters", async () => {
      await page.getByRole("button", { name: "Clear filters" }).click();

      await expect(page.getByLabel("Site contains atl1")).not.toBeVisible();
      await expect(page.getByLabel("Tags contains blue")).not.toBeVisible();

      await expect(page.getByRole("link", { name: "atl1-core1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "den1-edge1" })).toBeVisible();
    });
  });

  test("should correctly display the filters with hierarchical dropdown pointing to any nodes", async ({
    page,
  }) => {
    await page.goto("/objects/CoreArtifact");

    await page.getByTestId("object-items").getByRole("button", { name: "Object" }).click();
    await page.getByLabel("Kind").click();
    await page.getByRole("option", { name: "BGP Session Infra" }).click();
    await expect(page.getByLabel("BGP Session")).toBeVisible();
  });

  test("should correctly filter from a kind", async ({ page }) => {
    await page.goto("/objects/InfraInterface");
    await expect(page.getByTestId("object-items")).toContainText("Interface L2");
    await expect(page.getByTestId("object-items")).toContainText("Interface L3");

    await test.step("filter using kind", async () => {
      await page.getByRole("button", { name: "Kind", exact: true }).click();
      await page.getByLabel("Kind").click();
      await page.getByRole("option", { name: "Interface L3 Infra", exact: true }).click();
      await page.getByRole("button", { name: "Filter" }).click();

      await expect(page.getByLabel("Kind contains InfraInterfaceL3")).toBeVisible();
      await expect(page.getByTestId("object-items")).toContainText("Interface L3");
      await expect(page.getByTestId("object-items")).not.toContainText("Interface L2");
    });

    await test.step("clear kind filter", async () => {
      await page.getByLabel("Kind contains InfraInterfaceL3").click();

      await expect(page.getByTestId("object-items")).toContainText("Interface L2");
      await expect(page.getByTestId("object-items")).toContainText("Interface L3");
    });
  });
});
