import { expect, test } from "@playwright/test";

test.describe("Tasks - READ", () => {
  test("should correctly access to the tasks list and details", async ({ page }) => {
    await page.goto("/tasks");
    await expect(page.getByRole("heading", { name: "Task Overview" })).toBeVisible();
    await expect(page.getByRole("link", { name: "All tasks" })).toBeVisible();
    await expect(page.getByText("StateSCHEDULED")).toBeVisible();
  });
});
