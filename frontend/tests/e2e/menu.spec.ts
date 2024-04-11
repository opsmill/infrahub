import { expect, test } from "@playwright/test";

test.describe("Sidebar menu", () => {
  test("filter item in menu", async ({ page }) => {
    await page.goto("/");

    await test.step("all items are visible", async () => {
      await expect(page.getByRole("button", { name: "BGP Session" })).toBeVisible();
      await expect(page.getByRole("link", { name: "All BGP Session(s)" })).toBeVisible();
      await expect(page.getByRole("link", { name: "BGP Peer Group" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Circuit" })).toBeVisible();
    });

    await test.step("filter with text 'inter'", async () => {
      await page.getByTestId("search-menu").fill("inter");
    });

    await test.step("only items who includes 'bgp' are visible", async () => {
      await expect(page.getByRole("button", { name: "Device" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Interface L2" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Interface L3" })).toBeVisible();
    });
  });
});
