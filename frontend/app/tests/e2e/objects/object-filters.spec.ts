import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("Object filters", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

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
      await page.getByRole("option", { name: "Edge Router" }).click();
      await page.getByRole("button", { name: "Apply" }).click();

      await expect(
        page.getByLabel("Active filters").getByLabel("Role contains edge")
      ).toBeVisible();
      await expect(page.getByRole("button", { name: "Clear filters" })).toBeVisible();

      await expect(page.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "den1-edge1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "atl1-core1" })).not.toBeVisible();

      await page.getByRole("button", { name: "Role" }).click();
      await expect(page.getByTestId("attribute-filter-form")).toContainText("Edge Router");
    });

    await test.step("filter using a relationship of cardinality one", async () => {
      await page.getByRole("button", { name: "Site" }).click();
      await page.getByRole("option", { name: "atl1" }).click();
      await page
        .getByTestId("relationship-filter-form")
        .getByRole("button", { name: "Apply" })
        .click();

      await expect(
        page.getByLabel("Active filters").getByLabel("Site contains atl1")
      ).toBeVisible();
      await expect(page.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "den1-edge1" })).not.toBeVisible();
      await expect(page.getByRole("link", { name: "atl1-core1" })).not.toBeVisible();

      await page.getByRole("button", { name: "Site" }).click();
      await expect(page.getByTestId("relationship-filter-form")).toContainText("atl1×");
      await page.getByText("Filter by Site").press("Escape");
      await expect(page.getByTestId("relationship-filter-form")).not.toBeVisible();
    });

    await test.step("remove an attribute filter", async () => {
      await page.getByLabel("Active filters").getByLabel("Role contains edge").click();

      await expect(page.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "atl1-core1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "den1-edge1" })).not.toBeVisible();
    });

    await test.step("filter using a relationship of cardinality many", async () => {
      await page.getByRole("button", { name: "Tags" }).click();
      await page.getByRole("option", { name: "blue" }).click();
      await page.getByRole("button", { name: "Apply" }).click();

      await expect(
        page.getByLabel("Active filters").getByLabel("Site contains atl1")
      ).toBeVisible();
      await expect(
        page.getByLabel("Active filters").getByLabel("Tags contains blue")
      ).toBeVisible();

      await expect(page.getByRole("link", { name: "atl1-core1" })).toBeVisible();
      await expect(page.getByRole("link", { name: "atl1-edge1" })).not.toBeVisible();
      await expect(page.getByRole("link", { name: "den1-edge1" })).not.toBeVisible();

      await page.getByRole("button", { name: "Tags" }).click();
      await expect(page.getByTestId("relationship-filter-form")).toContainText("blue×");
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

  test("should correctly filter from a kind", async ({ page }) => {
    await page.goto("/objects/InfraInterface");
    await expect(page.getByTestId("object-items")).toContainText("Interface L2");
    await expect(page.getByTestId("object-items")).toContainText("Interface L3");
    await expect(page.getByTestId("object-schema-schema-selector")).toContainText("All Interface");

    await test.step("filter target kind", async () => {
      await page.getByTestId("object-schema-schema-selector").click();
      await expect(page.getByTestId("object-schema-schema-selector-popover")).toBeVisible();
      await expect(
        page.getByRole("option", { name: "Interface L2 Infra", exact: true })
      ).toBeVisible();
      await expect(
        page.getByRole("option", { name: "Interface L3 Infra", exact: true })
      ).toBeVisible();
      await page.getByPlaceholder("Filter...").fill("l3");
      await expect(
        page.getByRole("option", { name: "Interface L2 Infra", exact: true })
      ).toBeHidden();
      await expect(
        page.getByRole("option", { name: "Interface L3 Infra", exact: true })
      ).toBeVisible();
    });

    await test.step("filter using kind", async () => {
      await page.getByRole("option", { name: "Interface L3 Infra", exact: true }).click();
      await expect(page.getByTestId("object-schema-schema-selector-popover")).not.toBeVisible();

      await expect(page.getByTestId("object-schema-schema-selector")).toContainText(
        "Interface L3Infra"
      );
      await expect(page.getByTestId("object-items")).toContainText("Interface L3");
      await expect(page.getByTestId("object-items")).not.toContainText("Interface L2");
    });

    await test.step("clear kind filter", async () => {
      await page.getByTestId("object-schema-schema-selector").click();
      await page.getByRole("option", { name: "All Interface", exact: true }).click();

      await expect(page.getByTestId("object-items")).toContainText("Interface L2");
      await expect(page.getByTestId("object-items")).toContainText("Interface L3");
    });
  });

  test("should filter using enum value", async ({ page }) => {
    await page.goto("/objects/InfraBGPSession");
    await expect(page.getByTestId("object-items")).toContainText("EXTERNAL");
    await expect(page.getByTestId("object-items")).toContainText("INTERNAL");

    await page.getByRole("button", { name: "Type" }).click();
    await expect(page.getByPlaceholder("Filter...")).toBeFocused();
    await expect(page.getByRole("option", { name: "EXTERNAL" })).toBeVisible();
    await expect(page.getByRole("option", { name: "INTERNAL" })).toBeVisible();
    await page.getByRole("option", { name: "EXTERNAL" }).click();
    await expect(page.getByRole("combobox").filter({ hasText: "EXTERNAL" })).toBeVisible();
    await page.getByRole("button", { name: "Apply" }).click();

    await expect(page.getByRole("row", { name: "Type contains EXTERNAL" })).toBeVisible();
    await expect(page.getByTestId("object-items")).toContainText("EXTERNAL");
    await expect(page.getByTestId("object-items")).not.toContainText("INTERNAL");

    await page.getByRole("button", { name: "Type" }).click();
    await expect(page.getByRole("combobox").filter({ hasText: "EXTERNAL" })).toBeVisible();

    await page.getByRole("row", { name: "Type contains EXTERNAL" }).click();
    await expect(page.getByTestId("object-items")).toContainText("EXTERNAL");
    await expect(page.getByTestId("object-items")).toContainText("INTERNAL");
  });
});
