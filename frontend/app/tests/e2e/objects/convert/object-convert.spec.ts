import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../../constants";

test.describe.fixme("Object details - convert", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("should access the convert page", async ({ page }) => {
    await page.goto("http://localhost:8080/objects/InfraInterface");
    await page.getByRole("link", { name: "atl1-edge1, Ethernet1", exact: true }).click();
    await page.getByTestId("object-details-action-button").click();
    await page.getByRole("menuitem", { name: "Convert object type" }).click();
    await expect(page.getByText("SOURCE")).toBeVisible();
    await expect(page.getByText("NameEthernet1")).toBeVisible();
  });
});
