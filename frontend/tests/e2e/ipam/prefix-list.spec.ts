import { expect, test } from "@playwright/test";

test.describe("/ipam/prefixes - Prefix list", () => {
  test("view the prefix list, use the pagination and view prefix summary", async ({ page }) => {
    await page.goto("/ipam/prefixes");
    await page.getByTestId("select-open-option-button").click();
    await page.getByRole("option", { name: "20" }).click();
    await page
      .getByTestId("ipam-main-content")
      .getByRole("link", { name: "203.0.113.0/24" }) // prefix need pagination to be visible
      .click();
    expect(page.url()).toContain("/ipam/prefixes/");
    await expect(page.getByText("Ipam IPPrefix summary")).toBeVisible();
    await expect(page.getByText("Prefix203.0.113.0/24")).toBeVisible();
    await expect(page.getByText("Utilization93%")).toBeVisible();
    await expect(page.getByRole("progressbar")).toBeVisible();
    await expect(page.getByText("Ip Namespacedefault")).toBeVisible();
  });
});
