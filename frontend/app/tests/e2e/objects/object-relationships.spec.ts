import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("/objects/:objectKind/:objectId - relationship tab", () => {
  test.describe.configure({ mode: "serial" });
  const BRANCH_NAME = generateRandomBranchName("object-relationships");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test.describe("when not logged in", () => {
    test("should not be able to edit relationship", async ({ page }) => {
      await test.step("Navigate to relationship tab of an object", async () => {
        await page.goto(`/objects/InfraPlatform?branch=${BRANCH_NAME}`);
        await page.getByRole("link", { name: "Cisco IOS", exact: true }).click();
      });

      await test.step("all buttons are disabled", async () => {
        await expect(page.getByTestId("edit-button")).toBeDisabled();

        await page.getByTestId("object-details-menu").click();
        await expect(page.getByRole("menuitem", { name: "Groups" })).toHaveAttribute(
          "aria-disabled",
          "true"
        );
        await expect(page.getByRole("menuitem", { name: "Delete" })).toHaveAttribute(
          "aria-disabled",
          "true"
        );
        await page.keyboard.press("Escape");

        await page.getByRole("link", { name: "Devices 10" }).click();
        await expect(page.getByTestId("open-relationship-form-button")).toBeDisabled();
      });
    });
  });

  test.describe("when logged in as Admin", () => {
    test.describe.configure({ mode: "serial" });
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should delete the relationship", async ({ page }) => {
      await test.step("Navigate to relationship tab of an object", async () => {
        await page.goto(`/objects/InfraPlatform?branch=${BRANCH_NAME}`);
        await page.getByRole("link", { name: "Cisco IOS", exact: true }).click();
        await page.getByRole("link", { name: "Devices 10" }).click();
      });

      await test.step("Delete the relationship", async () => {
        await page.getByTestId("actions-cell-atl1-leaf1").click();
        await page.getByRole("menuitem", { name: "Dissociate" }).click();
        await expect(
          page.getByText(
            "Are you sure you want to dissociate atl1-leaf1 ?- This action will only remove the association.- The object itself will not be deleted."
          )
        ).toBeVisible();
        await page.getByTestId("modal-delete-confirm").click();
      });

      await test.step("Verify deletion of relationship", async () => {
        await expect(page.getByText("Association with atl1-leaf1")).toBeVisible();
        await expect(page.getByRole("link", { name: "atl1-leaf1" })).toBeHidden();
        await expect(page.getByRole("link", { name: "Devices 9" })).toBeVisible();
      });
    });

    test("should add a new relationship", async ({ page }) => {
      await test.step("Navigate to relationship tab of an object", async () => {
        await page.goto(`/objects/InfraPlatform?branch=${BRANCH_NAME}`);
        await page.getByRole("link", { name: "Cisco IOS", exact: true }).click();
        await page.getByRole("link", { name: "Devices 9" }).click();
        await expect(page.getByRole("link", { name: "atl1-leaf2" })).toBeVisible();
      });

      await test.step("Add a new relationship", async () => {
        await page.getByTestId("open-relationship-form-button").click();
        await page.getByTestId("side-panel-container").getByLabel("Devices").click();
        await page.getByRole("option", { name: "atl1-leaf1" }).click();
        await page.getByRole("button", { name: "Save" }).click();
      });

      await test.step("Verify new relationship addition", async () => {
        await expect(page.getByText("Association with InfraDevice added")).toBeVisible();
        await expect(page.getByRole("link", { name: "Devices 10" })).toBeVisible();
        await expect(page.getByRole("link", { name: "atl1-leaf1" })).toBeVisible();
      });
    });

    test("should edit a relationship", async ({ page }) => {
      await test.step("Navigate to relationship tab of an object", async () => {
        await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);
        await page.getByRole("link", { name: "atl1-core1" }).click();
        await page.getByText("Interfaces6").click();
      });

      await test.step("Edit a relationship", async () => {
        await page.getByRole("link", { name: "Loopback0", exact: true }).click();
        await expect(page.getByText("NameLoopback0")).toBeVisible();

        await page.getByTestId("edit-button").click();
        await expect(page.getByText("Device *")).toBeVisible();
        await page.getByRole("textbox", { name: "Name *" }).fill("Loopback0-update");
        await page.getByRole("button", { name: "Save" }).click();
      });

      await test.step("Verify relationship update", async () => {
        await expect(page.getByText("InterfaceL3 updated")).toBeVisible();
        await expect(page.getByText("NameLoopback0-update")).toBeVisible();
      });
    });

    test("should access relationships of cardinality many with hierarchical children", async ({
      page,
    }) => {
      await test.step("Navigates to North America and checks the children", async () => {
        await page.goto(`/objects/LocationContinent?branch=${BRANCH_NAME}`);
        await page.getByRole("link", { name: "North America" }).first().click();
        await page.getByText("Children2").click();
        await expect(page.getByRole("link", { name: "Canada" })).toBeVisible();
        await expect(page.getByRole("link", { name: "United States of America" })).toBeVisible();
      });

      await test.step("Navigates to the USA and checks the children", async () => {
        await page.getByRole("link", { name: "United States of America" }).click();
        await page.getByText("Children5").click();
        await expect(page.getByRole("link", { name: "atl1" })).toBeVisible();
        await expect(page.getByRole("link", { name: "den1" })).toBeVisible();
        await expect(page.getByText("Bailey Li")).toBeVisible();
        await expect(page.getByText("Francesca Wilcox")).toBeVisible();
      });
    });

    test("should access to the pool selector on relationships add", async ({ page }) => {
      await page.goto(`/objects/InfraInterfaceL3?branch=${BRANCH_NAME}`);
      await page
        .getByTestId("identifier-cell")
        .getByRole("link", { name: "Ethernet1", exact: true })
        .nth(2)
        .click();
      await page.getByText("Ip Addresses0").click();
      await page.getByTestId("open-relationship-form-button").click();
      await page.getByTestId("select-open-pool-option-button").click();
      await expect(page.getByRole("option", { name: "Loopbacks pool" })).toBeVisible();
    });
  });

  test("clicking on a relationship value redirects to its details page", async ({ page }) => {
    await test.step("Navigate to relationship tab of an object", async () => {
      await page.goto(`/objects/InfraPlatform?branch=${BRANCH_NAME}`);
      await page.getByRole("link", { name: "Cisco IOS", exact: true }).click();
      await page.getByRole("link", { name: "Devices 10" }).click();
    });
    await page.getByRole("link", { name: "atl1", exact: true }).first().click();
    await expect(page.getByTestId("object-details").getByText("Nameatl1")).toBeVisible();
    expect(page.url()).toContain("/objects/LocationSite/");
  });
});
