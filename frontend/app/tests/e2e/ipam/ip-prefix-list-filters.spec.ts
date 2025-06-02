import { expect, test } from "@playwright/test";

test.describe("IP Prefix List Filters", () => {
  test("view the prefix list, use the pagination and view prefix summary", async ({ page }) => {
    await page.goto("/ipam");

    await expect(
      page.getByTestId("identifier-cell").getByRole("link", { name: "10.0.0.0/8" })
    ).toBeVisible();
    await expect(
      page.getByTestId("identifier-cell").getByRole("link", { name: "10.0.0.0/16" })
    ).toBeVisible();
    await expect(
      page.getByTestId("identifier-cell").getByRole("link", { name: "10.1.0.0/16" })
    ).toBeVisible();

    await page.getByPlaceholder("Search IP Prefix").fill("10.0.0.0/");

    await expect(
      page.getByTestId("identifier-cell").getByRole("link", { name: "10.0.0.0/8" })
    ).toBeVisible();
    await expect(
      page.getByTestId("identifier-cell").getByRole("link", { name: "10.0.0.0/16" })
    ).toBeVisible();
    await expect(
      page.getByTestId("identifier-cell").getByRole("link", { name: "10.1.0.0/16" })
    ).not.toBeVisible();

    await page.getByRole("button", { name: "Member Type" }).click();
    await page.getByRole("option", { name: "Prefix Prefix serves as" }).click();
    await page.getByRole("button", { name: "Apply" }).click();

    await expect(
      page.getByTestId("identifier-cell").getByRole("link", { name: "10.0.0.0/8" })
    ).toBeVisible();
    await expect(
      page.getByTestId("identifier-cell").getByRole("link", { name: "10.0.0.0/16" })
    ).not.toBeVisible();
  });
});
