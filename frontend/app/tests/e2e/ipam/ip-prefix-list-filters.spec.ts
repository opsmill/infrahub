import { expect, test } from "@playwright/test";

test.describe("/ipam - IP Prefix List Filtering", () => {
  test("should filter IP prefixes by search text and column filtering", async ({ page }) => {
    await page.goto("/ipam");

    await test.step("verify initial prefix list", async () => {
      await expect(
        page.getByTestId("identifier-cell").getByRole("link", { name: "10.0.0.0/8" })
      ).toBeVisible();
      await expect(
        page.getByTestId("identifier-cell").getByRole("link", { name: "10.0.0.0/16" })
      ).toBeVisible();
      await expect(
        page.getByTestId("identifier-cell").getByRole("link", { name: "10.1.0.0/16" })
      ).toBeVisible();
    });

    await test.step("filter prefixes by search text", async () => {
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
    });

    await test.step("further filter using column filtering", async () => {
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
});
