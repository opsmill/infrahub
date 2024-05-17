import { expect, test } from "@playwright/test";

test.describe("Sidebar menu", () => {
  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

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

    await test.step("only items who includes 'inter' are visible", async () => {
      await expect(page.getByRole("button", { name: "Device" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Interface", exact: true })).toBeVisible();
      await expect(page.getByRole("link", { name: "MLAG Interface", exact: true })).toBeVisible();
    });
  });

  test("display groups and all items when group matches but no items matches", async ({ page }) => {
    await page.goto("/");

    await page.getByTestId("search-menu").fill("ipam");

    await test.step("all items under Ipam group are visible", async () => {
      await expect(page.getByRole("button", { name: "IPAM" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Namespaces" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Prefixes" })).toBeVisible();
      await expect(page.getByRole("link", { name: "IP Addresses" })).toBeVisible();
    });
  });

  test("display no items nor groups when there is no match", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("button", { name: "Objects" })).toBeVisible();

    await page.getByTestId("search-menu").fill("no-item-found");

    await expect(page.getByTestId("sidebar-menu").getByRole("link")).toBeHidden();
  });
});
