import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../../constants";
import { generateRandomBranchName, saveScreenshotForDocs } from "../../../utils";
import { createBranchAPI, deleteBranchAPI } from "../../utils/graphql";

test.describe("Object details - convert", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  const BRANCH_NAME = generateRandomBranchName("object-convert");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should convert an Interface L3 to an Interface L2", async ({ page }) => {
    await test.step("access object details and convert page", async () => {
      await page.goto(`/objects/InfraInterface?branch=${BRANCH_NAME}`);
      await page.getByRole("link", { name: "atl1-edge1, Ethernet1", exact: true }).click();
      await page.getByTestId("object-details-button").click();
      await saveScreenshotForDocs(page, "object_convert_button");
      await page.getByRole("menuitem", { name: "Convert object type" }).click();
      await expect(page.getByText("SOURCE")).toBeVisible();
      await expect(page.getByText("NameEthernet1")).toBeVisible();
      await expect(page.getByText("Deviceatl1-edge1")).toBeVisible();
    });

    await test.step("display the interface L3 form with default values from the source object", async () => {
      await page.getByText("Select target object type").click();
      await page.getByPlaceholder("Filter...").fill("l2");
      await page.getByRole("option", { name: "Interface L2 Infra", exact: true }).click();
      await expect(
        page.getByRole("combobox").filter({ hasText: "atl1-edge1• Device" })
      ).toBeVisible();
      await saveScreenshotForDocs(page, "object_convert_mapping");
      await page.getByRole("combobox").filter({ hasText: "atl1-edge1• Device" }).click();

      await expect(page.getByRole("option", { name: "atl1-edge1 Matched Device" })).toBeVisible();

      await expect(page.getByRole("combobox").filter({ hasText: "Ethernet1• Name" })).toBeVisible();
      await expect(
        page.getByRole("combobox").filter({ hasText: "Ethernet1• Connected Endpoint" })
      ).toBeVisible();
      await expect(
        page.getByRole("combobox").filter({ hasText: "Connected to atl1-edge2::" })
      ).toBeVisible();
      await expect(page.getByRole("combobox").filter({ hasText: "• LACP Priority" })).toBeVisible();
      await expect(page.getByRole("combobox").filter({ hasText: "• Enabled" })).toBeVisible();
      await expect(page.getByRole("combobox").filter({ hasText: "Active• Status" })).toBeVisible();
      await expect(page.getByRole("combobox").filter({ hasText: "Peer• Role" })).toBeVisible();
    });

    await test.step("select other values from the source object", async () => {
      // Select an option from the dropdown
      await page.getByRole("combobox", { name: "Layer2 Mode *" }).click();
      await page.getByRole("option", { name: "Access" }).click();

      // Select an option for the text value from another field in the source object
      await page.getByRole("combobox").filter({ hasText: "Ethernet1• Name" }).click();
      await expect(page.getByRole("option", { name: "Ethernet1 Matched Name" })).toBeVisible();
      await expect(page.getByRole("option", { name: "Connected to atl1-edge2::" })).toBeVisible();
      await page.getByRole("option", { name: "Connected to atl1-edge2::" }).click();

      // Select an option for the number value from another field in the source object
      await page.getByRole("combobox").filter({ hasText: "• LACP Priority" }).click();
      await expect(page.getByRole("option", { name: "Matched LACP Priority" })).toBeVisible();
      await expect(page.getByRole("option", { name: "Speed" })).toBeVisible();
      await page.getByText("10000Speed").click();
      await expect(
        page
          .locator("div")
          .filter({ hasText: /^LACP Priority Number10000• SpeedFrom sourceCustom value$/ })
          .getByRole("combobox")
      ).toBeVisible();

      // Select an option for the dropdown value from another field in the source object
      await page.getByRole("combobox").filter({ hasText: "Active• Status" }).click();
      await expect(page.getByRole("option", { name: "Active Matched Status" })).toBeVisible();
    });

    await test.step("select other values from the source object", async () => {
      // Submit and check object values
      await page.getByRole("button", { name: "Convert", exact: true }).click();
      await expect(page.getByText("Successfully converted")).toBeVisible();
      await expect(page.getByText("NameConnected to atl1-edge2::")).toBeVisible();
      await page.getByText("LACP Priority10000").click();
      await expect(
        page.getByTestId("breadcrumb-navigation").getByRole("link", { name: "Interface L2" })
      ).toBeVisible();
    });
  });
});
