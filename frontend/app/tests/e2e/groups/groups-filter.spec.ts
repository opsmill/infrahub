import { expect, test } from "@playwright/test";

test.describe("CoreGroup filtering", () => {
  test("toggles visibility of internal groups", async ({ page }) => {
    await page.goto("/objects/CoreGroup");

    const showInternalGroupsFilter = page.getByRole("row", { name: "internal groups is hidden" });
    const hideInternalGroupsFilter = page.getByRole("row", { name: "Hide internal groups" });
    const engineeringTeamLink = page
      .getByTestId("object-items")
      .getByRole("link", { name: "Engineering Team" });
    const computedGroupLink = page
      .getByTestId("object-items")
      .getByRole("link", { name: "computed_" })
      .first();

    await expect(showInternalGroupsFilter).toBeVisible();
    await expect(engineeringTeamLink).toBeVisible();
    await expect(computedGroupLink).toBeHidden();

    await showInternalGroupsFilter.click();

    await expect(hideInternalGroupsFilter).toBeVisible();
    await expect(engineeringTeamLink).toBeVisible();
  });
});
