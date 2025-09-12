import { expect, test } from "@playwright/test";

import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

test.describe("CoreGroup filtering", () => {
  const BRANCH_NAME = generateRandomBranchName("groups-filter");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("toggles visibility of internal groups", async ({ page }) => {
    await page.goto("/objects/CoreGroup");

    const showInternalGroupsFilter = page.getByLabel("internal groups contains hidden");
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
