import { expect, test } from "@playwright/test";

test.describe("Object filters", () => {
  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("should filter the objects list", async ({ page }) => {
    await test.step("access objects list and verify initial state", async () => {
      await page.goto("/objects/InfraDevice");
      await expect(page.getByTestId("object-items")).toContainText("Filters: 0");
      await expect(page.getByTestId("object-items")).toContainText("Showing 1 to 10 of 30 results");
    });

    await test.step("start filtering objects", async () => {
      await test.step("select filters", async () => {
        await page.getByTestId("apply-filters").click();
        await page.getByLabel("Role").click();
        await page.getByRole("option", { name: "Edge Router" }).click();

        const tagsMultiSelectOpenButton = page
          .getByTestId("side-panel-container")
          .getByText("Tags")
          .locator("../..")
          .getByTestId("select-open-option-button");
        await tagsMultiSelectOpenButton.click();

        await page.getByTestId("side-panel-container").getByText("red").click();

        // Closes the multiselect
        await tagsMultiSelectOpenButton.click();

        await page.getByRole("button", { name: "Apply filters" }).scrollIntoViewIfNeeded();
        await page.getByRole("button", { name: "Apply filters" }).click();
      });

      await test.step("verify filter initial value", async () => {
        await page.getByTestId("apply-filters").click();

        await expect(page.getByLabel("Role")).toHaveText("Edge Router");
      });

      await expect(page.locator("form")).toContainText("red");

      await page.getByRole("button", { name: "Apply filters" }).scrollIntoViewIfNeeded();
      await page.getByRole("button", { name: "Apply filters" }).click();
    });

    await test.step("verify new state", async () => {
      await expect(page.getByTestId("object-items")).toContainText("Filters: 2");
      await expect(page.getByTestId("object-items")).toContainText("Showing 1 to 10 of 10 results");
    });

    await test.step("remove filters and verify initial state", async () => {
      await page.getByTestId("remove-filters").click();
      await expect(page.getByTestId("object-items")).toContainText("Filters: 0");
      await expect(page.getByTestId("object-items")).toContainText("Showing 1 to 10 of 30 results");
    });
  });

  test("should filter using a relationship of cardinality one", async ({ page }) => {
    await page.goto("/objects/InfraInterface");

    await expect(page.getByRole("link", { name: "Connected to jfk1-edge2" })).toBeVisible();

    await page.getByTestId("apply-filters").click();
    await page
      .getByTestId("side-panel-container")
      .getByText("Device")
      .locator("../..")
      .getByTestId("select-open-option-button")
      .click();
    await page.getByRole("option", { name: "atl1-core1" }).click();
    await page.getByRole("button", { name: "Apply filters" }).click();

    await expect(page.getByRole("row", { name: "InfraInterfaceL3 Loopback0" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Connected to jfk1-edge2" })).toBeHidden();
  });

  test("should correctly display the filters with hierarchical dropdown pointing to any objects", async ({
    page,
  }) => {
    await page.goto("/objects/CoreArtifact");
    await page.getByTestId("apply-filters").click();
    await expect(page.getByTestId("side-panel-container").getByText("Object")).toBeVisible();

    await page.getByLabel("kind").click();
    await expect(page.getByRole("option", { name: "Tag Builtin", exact: true })).toBeVisible();
  });

  test("should correctly filter from a kind", async ({ page }) => {
    await page.goto("/objects/InfraInterface");
    await page.getByTestId("apply-filters").click();

    await test.step("profiles selector should not be visible", async () => {
      await expect(page.getByText("Select an object type")).not.toBeVisible();
    });

    await test.step("filter objects", async () => {
      await page.getByLabel("kind").click();
      await page.getByRole("option", { name: "Interface L2 Infra", exact: true }).click();
      await page.getByRole("button", { name: "Apply filters" }).click();
      await expect(page.getByTestId("object-items")).toContainText(
        "Showing 1 to 10 of 510 results"
      );
    });

    await test.step("verify filter initial value", async () => {
      await page.getByTestId("apply-filters").click();
      await expect(page.getByLabel("Kind")).toContainText("Interface L2 Infra");
    });
  });
});
