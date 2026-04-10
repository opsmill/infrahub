import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("Object filters", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.describe("using the filter picker", () => {
    test("should filter by attribute, relationship, and node metadata with all conditions", async ({
      page,
    }) => {
      await test.step("navigate and verify initial state", async () => {
        await page.goto("/objects/InfraDevice");
        await expect(page.getByRole("heading", { name: "Device" })).toBeVisible();
        await expect(page.getByRole("link", { name: "atl1-core1" })).toBeVisible();
        await expect(page.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
        await expect(page.getByRole("link", { name: "den1-edge1" })).toBeVisible();
      });

      await test.step("filter by attribute with 'contains' condition", async () => {
        await page.getByRole("button", { name: "Filter" }).click();
        await expect(page.getByRole("listbox", { name: "Filter fields" })).toBeVisible();

        await page
          .getByRole("listbox", { name: "Filter fields" })
          .getByRole("option", { name: "Role" })
          .click();
        await expect(page.getByTestId("attribute-filter-form")).toBeVisible();

        await page.getByRole("option", { name: "Edge Router" }).click();
        await page
          .getByTestId("attribute-filter-form")
          .getByRole("button", { name: "Apply" })
          .click();

        await expect(page.getByRole("row", { name: "Role contains edge" })).toBeVisible();
        await expect(page.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
        await expect(page.getByRole("link", { name: "den1-edge1" })).toBeVisible();
        await expect(page.getByRole("link", { name: "atl1-core1" })).not.toBeVisible();
      });

      await test.step("update attribute filter value", async () => {
        await page.getByRole("row", { name: "Role contains edge" }).click();
        await expect(page.getByTestId("attribute-filter-form")).toBeVisible();

        await page.getByRole("option", { name: "Core Router" }).click();
        await page
          .getByTestId("attribute-filter-form")
          .getByRole("button", { name: "Apply" })
          .click();

        await expect(page.getByRole("row", { name: "Role contains core" })).toBeVisible();
        await expect(page.getByRole("link", { name: "atl1-core1" })).toBeVisible();
        await expect(page.getByRole("link", { name: "atl1-edge1" })).not.toBeVisible();
      });

      await test.step("clear filters", async () => {
        await page.getByTestId("filter-reset-button").click();
        await expect(page.getByRole("row", { name: "Role contains core" })).not.toBeVisible();
        await expect(page.getByRole("link", { name: "atl1-core1" })).toBeVisible();
        await expect(page.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
      });

      await test.step("filter by relationship with 'is any of' condition", async () => {
        await page.getByRole("button", { name: "Filter" }).click();
        await page
          .getByRole("listbox", { name: "Filter fields" })
          .getByRole("option", { name: "Site" })
          .click();
        await expect(page.getByTestId("relationship-filter-form")).toBeVisible();

        await page.getByRole("option", { name: "atl1" }).click();
        await page
          .getByTestId("relationship-filter-form")
          .getByRole("button", { name: "Apply" })
          .click();

        await expect(page.getByRole("row", { name: /Site.*is any of.*atl1/ })).toBeVisible();
        await expect(page.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
        await expect(page.getByRole("link", { name: "den1-edge1" })).not.toBeVisible();
      });

      await test.step("clear filters", async () => {
        await page.getByTestId("filter-reset-button").click();
      });

      await test.step("filter by attribute with 'is empty' condition", async () => {
        await page.getByRole("button", { name: "Filter" }).click();
        await page
          .getByRole("listbox", { name: "Filter fields" })
          .getByRole("option", { name: "Name" })
          .click();

        await page.getByRole("button", { name: /select a condition/ }).click();
        await page.getByRole("option", { name: "is empty" }).click();
        await page
          .getByTestId("attribute-filter-form")
          .getByRole("button", { name: "Apply" })
          .click();

        await expect(page.getByRole("row", { name: "Name is empty" })).toBeVisible();
      });

      await test.step("clear filters", async () => {
        await page.getByTestId("filter-reset-button").click();
      });

      await test.step("filter by attribute with 'is not empty' condition", async () => {
        await page.getByRole("button", { name: "Filter" }).click();
        await page
          .getByRole("listbox", { name: "Filter fields" })
          .getByRole("option", { name: "Name" })
          .click();

        await page.getByRole("button", { name: /select a condition/ }).click();
        await page.getByRole("option", { name: "is not empty" }).click();
        await page
          .getByTestId("attribute-filter-form")
          .getByRole("button", { name: "Apply" })
          .click();

        await expect(page.getByRole("row", { name: "Name is not empty" })).toBeVisible();
      });

      await test.step("clear filters", async () => {
        await page.getByTestId("filter-reset-button").click();
      });

      await test.step("filter by relationship with 'is empty' condition", async () => {
        await page.getByRole("button", { name: "Filter" }).click();
        await page
          .getByRole("listbox", { name: "Filter fields" })
          .getByRole("option", { name: "Tags" })
          .click();

        await page.getByRole("button", { name: /select a condition/ }).click();
        await page.getByRole("option", { name: "is empty" }).click();
        await page
          .getByTestId("relationship-filter-form")
          .getByRole("button", { name: "Apply" })
          .click();

        await expect(page.getByRole("row", { name: "Tags is empty" })).toBeVisible();
      });

      await test.step("clear filters", async () => {
        await page.getByTestId("filter-reset-button").click();
      });

      await test.step("filter by relationship with 'is not empty' condition", async () => {
        await page.getByRole("button", { name: "Filter" }).click();
        await page
          .getByRole("listbox", { name: "Filter fields" })
          .getByRole("option", { name: "Tags" })
          .click();

        await page.getByRole("button", { name: /select a condition/ }).click();
        await page.getByRole("option", { name: "is not empty" }).click();
        await page
          .getByTestId("relationship-filter-form")
          .getByRole("button", { name: "Apply" })
          .click();

        await expect(page.getByRole("row", { name: "Tags is not empty" })).toBeVisible();
      });

      await test.step("clear filters", async () => {
        await page.getByTestId("filter-reset-button").click();
      });

      await test.step("filter by metadata date with 'after' condition", async () => {
        await page.getByRole("button", { name: "Filter" }).click();
        await page
          .getByRole("listbox", { name: "Filter fields" })
          .getByRole("option", { name: "Created at" })
          .click();
        await expect(page.getByTestId("metadata-date-filter-form")).toBeVisible();

        // Default condition is "after"
        await page
          .getByRole("option", { name: /Choose.*1st/ })
          .first()
          .click();
        await page
          .getByTestId("metadata-date-filter-form")
          .getByRole("button", { name: "Apply" })
          .click();

        await expect(page.getByRole("row", { name: /Created at.*after/ })).toBeVisible();
      });

      await test.step("clear filters", async () => {
        await page.getByTestId("filter-reset-button").click();
      });

      await test.step("filter by metadata date with 'before' condition", async () => {
        await page.getByRole("button", { name: "Filter" }).click();
        await page
          .getByRole("listbox", { name: "Filter fields" })
          .getByRole("option", { name: "Created at" })
          .click();

        await page.getByRole("button", { name: /select a condition/ }).click();
        await page.getByRole("option", { name: "before" }).click();

        await page
          .getByRole("option", { name: /Choose.*1st/ })
          .first()
          .click();
        await page
          .getByTestId("metadata-date-filter-form")
          .getByRole("button", { name: "Apply" })
          .click();

        await expect(page.getByRole("row", { name: /Created at.*before/ })).toBeVisible();
      });

      await test.step("clear filters", async () => {
        await page.getByTestId("filter-reset-button").click();
      });

      await test.step("filter by metadata user with 'is any of' condition", async () => {
        await page.getByRole("button", { name: "Filter" }).click();
        await page
          .getByRole("listbox", { name: "Filter fields" })
          .getByRole("option", { name: "Created by" })
          .click();
        await expect(page.getByTestId("metadata-user-filter-form")).toBeVisible();

        await page.getByRole("option", { name: /admin/i }).first().click();
        await page
          .getByTestId("metadata-user-filter-form")
          .getByRole("button", { name: "Apply" })
          .click();

        await expect(
          page.getByRole("row", { name: /Created by.*is any of.*admin/i })
        ).toBeVisible();
      });

      await test.step("clear all filters and verify initial state", async () => {
        await page.getByTestId("filter-reset-button").click();
        await expect(page.getByRole("link", { name: "atl1-core1" })).toBeVisible();
        await expect(page.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
        await expect(page.getByRole("link", { name: "den1-edge1" })).toBeVisible();
      });
    });
  });

  test.describe("using the column header", () => {
    test("should filter by attribute and relationship with all conditions", async ({ page }) => {
      await test.step("navigate and verify initial state", async () => {
        await page.goto("/objects/InfraDevice");
        await expect(page.getByRole("heading", { name: "Device" })).toBeVisible();
        await expect(page.getByRole("link", { name: "atl1-core1" })).toBeVisible();
        await expect(page.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
        await expect(page.getByRole("link", { name: "den1-edge1" })).toBeVisible();
      });

      await test.step("filter by attribute with 'contains' condition via column header", async () => {
        await page.getByRole("button", { name: "Role" }).click();
        await expect(page.getByText("Filter by Role")).toBeVisible();

        await page.getByRole("option", { name: "Edge Router" }).click();
        await page.getByRole("button", { name: "Apply" }).click();

        await expect(page.getByRole("row", { name: "Role contains edge" })).toBeVisible();
        await expect(page.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
        await expect(page.getByRole("link", { name: "den1-edge1" })).toBeVisible();
        await expect(page.getByRole("link", { name: "atl1-core1" })).not.toBeVisible();
      });

      await test.step("update attribute filter via column header", async () => {
        await page.getByTestId("object-items").getByRole("button", { name: "Role" }).click();
        await expect(page.getByTestId("attribute-filter-form")).toContainText("Edge Router");

        await page.getByRole("option", { name: "Core Router" }).click();
        await page.getByRole("button", { name: "Apply" }).click();

        await expect(page.getByRole("row", { name: "Role contains core" })).toBeVisible();
        await expect(page.getByRole("link", { name: "atl1-core1" })).toBeVisible();
        await expect(page.getByRole("link", { name: "atl1-edge1" })).not.toBeVisible();
      });

      await test.step("clear filters", async () => {
        await page.getByTestId("filter-reset-button").click();
      });

      await test.step("filter by attribute with 'is empty' condition via column header", async () => {
        await page.getByRole("button", { name: "Role" }).click();

        await page.getByRole("button", { name: /select a condition/ }).click();
        await page.getByRole("option", { name: "is empty" }).click();
        await page.getByRole("button", { name: "Apply" }).click();

        await expect(page.getByRole("row", { name: "Role is empty" })).toBeVisible();
      });

      await test.step("clear filters", async () => {
        await page.getByTestId("filter-reset-button").click();
      });

      await test.step("filter by attribute with 'is not empty' condition via column header", async () => {
        await page.getByRole("button", { name: "Role" }).click();

        await page.getByRole("button", { name: /select a condition/ }).click();
        await page.getByRole("option", { name: "is not empty" }).click();
        await page.getByRole("button", { name: "Apply" }).click();

        await expect(page.getByRole("row", { name: "Role is not empty" })).toBeVisible();
      });

      await test.step("clear filters", async () => {
        await page.getByTestId("filter-reset-button").click();
      });

      await test.step("filter by relationship with 'is any of' condition via column header", async () => {
        await page.getByRole("button", { name: "Site" }).click();
        await expect(page.getByText("Filter by Site")).toBeVisible();

        await page.getByRole("option", { name: "atl1" }).click();
        await page
          .getByTestId("relationship-filter-form")
          .getByRole("button", { name: "Apply" })
          .click();

        await expect(page.getByRole("row", { name: /Site.*is any of.*atl1/ })).toBeVisible();
        await expect(page.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
        await expect(page.getByRole("link", { name: "den1-edge1" })).not.toBeVisible();
      });

      await test.step("clear filters", async () => {
        await page.getByTestId("filter-reset-button").click();
      });

      await test.step("filter by relationship with 'is empty' condition via column header", async () => {
        await page.getByRole("button", { name: "Tags" }).click();

        await page.getByRole("button", { name: /select a condition/ }).click();
        await page.getByRole("option", { name: "is empty" }).click();
        await page
          .getByTestId("relationship-filter-form")
          .getByRole("button", { name: "Apply" })
          .click();

        await expect(page.getByRole("row", { name: "Tags is empty" })).toBeVisible();
      });

      await test.step("clear filters", async () => {
        await page.getByTestId("filter-reset-button").click();
      });

      await test.step("filter by relationship with 'is not empty' condition via column header", async () => {
        await page.getByRole("button", { name: "Tags" }).click();

        await page.getByRole("button", { name: /select a condition/ }).click();
        await page.getByRole("option", { name: "is not empty" }).click();
        await page
          .getByTestId("relationship-filter-form")
          .getByRole("button", { name: "Apply" })
          .click();

        await expect(page.getByRole("row", { name: "Tags is not empty" })).toBeVisible();
      });

      await test.step("update filter via filter tag click", async () => {
        await page.getByRole("row", { name: "Tags is not empty" }).click();

        const editPopover = page.getByRole("dialog").last();
        await editPopover.getByRole("button", { name: /select a condition/ }).click();
        await page.getByRole("option", { name: "is any of" }).click();

        await page.getByRole("option", { name: "blue" }).click();
        await editPopover.getByRole("button", { name: "Apply" }).click();

        await expect(page.getByRole("row", { name: /Tags.*is any of.*blue/ })).toBeVisible();
      });

      await test.step("clear all filters and verify initial state", async () => {
        await page.getByTestId("filter-reset-button").click();
        await expect(page.getByRole("link", { name: "atl1-core1" })).toBeVisible();
        await expect(page.getByRole("link", { name: "atl1-edge1" })).toBeVisible();
        await expect(page.getByRole("link", { name: "den1-edge1" })).toBeVisible();
      });
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

    await page.getByTestId("object-items").getByRole("button", { name: "Type" }).click();
    await expect(page.getByRole("combobox").filter({ hasText: "EXTERNAL" })).toBeVisible();
    await page.keyboard.press("Escape");

    await page.getByRole("button", { name: "Remove Type contains EXTERNAL" }).click();
    await expect(page.getByTestId("object-items")).toContainText("EXTERNAL");
    await expect(page.getByTestId("object-items")).toContainText("INTERNAL");
  });
});
