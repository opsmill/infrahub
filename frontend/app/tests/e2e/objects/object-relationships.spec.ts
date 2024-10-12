import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("/objects/:objectKind/:objectid - relationship tab", () => {
  // Avoid checking as non-admin + updating as admin at the same time
  test.describe.configure({ mode: "serial" });
  test.slow();

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test.describe("when not logged in", () => {
    test.skip("should not be able to edit relationship", async ({ page }) => {
      await test.step("Navigate to relationship tab of an object", async () => {
        await page.goto("/objects/InfraPlatform");
        await page.getByRole("link", { name: "Cisco IOS", exact: true }).click();
      });

      await test.step("all buttons are disabled", async () => {
        await expect(page.getByTestId("edit-button")).toBeDisabled();
        await expect(page.getByTestId("manage-groups")).toBeDisabled();
        await expect(page.getByTestId("delete-button")).toBeDisabled();

        await page.getByText("Devices10").click();
        await expect(page.getByTestId("open-relationship-form-button")).toBeDisabled();
      });
    });
  });

  test.describe("when logged in as Admin", () => {
    test.describe.configure({ mode: "serial" });
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should delete the relationship", async ({ page }) => {
      await test.step("Navigate to relationship tab of an object", async () => {
        await page.goto("/objects/InfraPlatform");
        await page.getByRole("link", { name: "Cisco IOS", exact: true }).click();
        await page.getByText("Devices10").click();
      });

      await test.step("Delete the relationship", async () => {
        await page
          .getByRole("row", { name: "ord1-leaf2" })
          .getByTestId("relationship-delete-button")
          .click();
        await expect(page.getByRole("paragraph")).toContainText(
          "Are you sure you want to remove the association between `Cisco IOS` and `ord1-leaf2`? The `InfraDevice` `ord1-leaf2` won't be deleted in the process."
        );
        await page.getByTestId("modal-delete-confirm").click();
      });

      await test.step("Verify deletion of relationship", async () => {
        await expect(page.getByRole("alert")).toContainText("Item removed from the group");
        await expect(page.getByText("Showing 1 to 9 of 9 results")).toBeVisible();
        await expect(page.getByLabel("Tabs")).toContainText("Devices9");
      });
    });

    test("should add a new relationship", async ({ page }) => {
      await test.step("Navigate to relationship tab of an object", async () => {
        await page.goto("/objects/InfraPlatform");
        await page.getByRole("link", { name: "Cisco IOS", exact: true }).click();
        await page.getByText("Devices9").click();
      });

      await test.step("Add a new relationship", async () => {
        await page.getByTestId("open-relationship-form-button").click();
        await page.getByTestId("side-panel-container").getByLabel("Devices").click();
        await page.getByRole("option", { name: "ord1-leaf2" }).click();
        await page.getByRole("button", { name: "Save" }).click();
      });

      await test.step("Verify new relationship addition", async () => {
        await expect(page.getByRole("alert")).toContainText("Association with InfraDevice added");
        await expect(page.getByText("Showing 1 to 10 of 10 results")).toBeVisible();
        await expect(page.getByLabel("Tabs")).toContainText("Devices10");
        await expect(page.getByRole("cell", { name: "ord1-leaf2" })).toBeVisible();
      });
    });

    test("should access relationships of cardinality many with hierarchical children", async ({
      page,
    }) => {
      await test.step("Navigates to North America and checks the children", async () => {
        await page.goto("/objects/LocationContinent");
        await page.getByRole("link", { name: "North America" }).first().click();
        await page.getByText("Children2").click();
        await expect(page.getByRole("link", { name: "Canada" })).toBeVisible();
        await expect(page.getByRole("link", { name: "United States of America" })).toBeVisible();
      });

      await test.step("Navigates to the USA and checks the children", async () => {
        await page.getByRole("link", { name: "United States of America" }).click();
        await page.getByText("Children5").click();
        await expect(page.getByRole("link", { name: "Atlanta" })).toBeVisible();
        await expect(page.getByRole("link", { name: "Denver" })).toBeVisible();
        await expect(page.getByRole("link", { name: "Bailey Li" })).toBeVisible();
        await expect(page.getByRole("link", { name: "Francesca Wilcox" })).toBeVisible();
      });
    });

    test("should access to the pool selector on relationships add", async ({ page }) => {
      await page.goto("/objects/InfraInterfaceL3/");
      await page.getByRole("link", { name: "Connected to den1-edge1::Ethernet1" }).click();
      await page.getByText("Ip Addresses1").click();
      await page.getByTestId("open-relationship-form-button").click();
      await expect(page.getByTestId("select-open-pool-option-button")).toBeVisible();
      await page
        .getByTestId("side-panel-container")
        .getByTestId("select-open-option-button")
        .click();
      await expect(page.getByTestId("relationship-row").first()).toBeVisible();
    });
  });

  test("clicking on a relationship value redirects to its details page", async ({ page }) => {
    await test.step("Navigate to relationship tab of an object", async () => {
      await page.goto("/objects/InfraPlatform");
      await page.getByRole("link", { name: "Cisco IOS", exact: true }).click();
      await page.getByText("Devices10").click();
    });
    await page.getByRole("link", { name: "atl1", exact: true }).first().click();
    await expect(page.getByText("Nameatl1")).toBeVisible();
    expect(page.url()).toContain("/objects/LocationSite/");
  });
});
