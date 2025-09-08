import { expect, test } from "@playwright/test";

import { saveScreenshotForDocs } from "../../utils";

test.describe.fixme("Tasks - READ", () => {
  test("should correctly access to the tasks list and details", async ({ page }) => {
    await page.goto("/tasks");
    await expect(page.getByRole("heading", { name: "Task Overview" })).toBeVisible();
    await saveScreenshotForDocs(page, "tasks_list");
    await page.getByRole("row", { name: "COMPLETED" }).getByRole("link").nth(1).click();
    await expect(page.getByRole("link", { name: "All tasks" })).toBeVisible();
    await expect(page.getByText("StateCOMPLETED")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Task Logs" })).toBeVisible();
  });
});
