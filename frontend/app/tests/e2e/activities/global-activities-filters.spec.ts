import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";

test.describe("Global Activities - List view and filter usage", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  test.slow();

  test("Filter by branch", async ({ page }) => {
    await page.goto("/activities");
    await page.getByRole("button", { name: "Branch" }).click();
    await page.getByRole("option", { name: "platform-conflict" }).click();
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(page.getByText("platform-conflict").nth(1)).toBeVisible();
    await page.getByRole("button", { name: "Branch platform-conflict" }).click();
    await expect(page.getByText("main").nth(1)).toBeVisible();
  });

  test("Filter by event type", async ({ page }) => {
    await page.goto("/activities");
    await page.getByRole("button", { name: "Event Type" }).click();
    await page.getByRole("option", { name: "Node created" }).click();
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(page.getByText("created").nth(1)).toBeVisible();
    await page.getByRole("button", { name: "Event Type" }).click();
    await expect(page.getByText("Node created")).toBeHidden();
    await page.getByRole("button", { name: "Event Type" }).click();
    await page.getByRole("option", { name: "Node deleted" }).click();
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(page.getByText("deleted").nth(1)).toBeVisible();
  });

  test("Filter by children", async ({ page }) => {
    await page.goto("/activities");
    await page.getByRole("button", { name: "Has Children" }).click();
    await page.getByText("True").click();
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(page.getByTestId("activity-has-children-icon").first()).toBeVisible();
  });

  test("Filter by nodes", async ({ page }) => {
    await page.goto("/activities");
    await page.getByRole("button", { name: "Primary Node" }).click();
    await page.getByRole("option", { name: "Account", exact: true }).click();
    await page.getByRole("option", { name: "Chloe O'Brian" }).click();
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(page.getByText("Chloe O'Brian").nth(1)).toBeVisible();
    await page.getByRole("button", { name: "Primary Node Chloe O'Brian" }).click();
    await page.getByRole("button", { name: "Related Node" }).click();
    await page.getByRole("option", { name: "Account", exact: true }).click();
    await page.getByRole("option", { name: "CRM Synchronization" }).click();
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(page.getByText("CRM Synchronization").nth(1)).toBeVisible();
  });

  test("Filter by account", async ({ page }) => {
    await page.goto("/activities");
    await page.getByRole("button", { name: "Account" }).click();
    await page.getByRole("option", { name: "Jack Bauer" }).click();
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(page.getByText("No activities found")).toBeVisible();
  });
});
