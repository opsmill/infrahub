import { expect, test } from "@playwright/test";

test.describe("/ipam/ip_addresses - IP Address list", () => {
  test("view the ip address list, use the pagination and view ip address summary", async ({
    page,
  }) => {
    await page.goto("/ipam/ip_addresses");

    await page.getByTestId("identifier-cell").getByRole("link", { name: "10.0.0.16/32" }).click();

    await expect(page.getByRole("heading", { name: "Details" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Activities" })).toBeVisible();

    await expect(page.getByRole("row", { name: "Address 10.0.0.16/32" })).toBeVisible();
    await expect(page.getByText("InterfaceLoopback0")).toBeVisible();
    await expect(page.getByRole("row", { name: "Ip Prefix 10.0.0.0/16" })).toBeVisible();
  });

  test("view all ip addresses under a given prefix", async ({ page }) => {
    await page.goto("/ipam");

    await test.step("select a prefix to view all ip addresses", async () => {
      await page.getByLabel("IPAM tree").getByText("172.16.0.0/16").click();
      await expect(page.getByRole("heading", { name: "172.16.0.0/16" })).toBeVisible();
      await page.getByRole("link", { name: "IP Addresses" }).click();
    });

    await test.step("click on any ip address row to view summary", async () => {
      await page.getByRole("link", { name: "172.16.0.1/16" }).click();
      await page.getByRole("heading", { name: "172.16.0.1/16" }).click();
      await page.getByRole("heading", { name: "Details" }).click();
      await page.getByRole("heading", { name: "Activities" }).click();
    });

    await test.step("use breadcrumb to go back to parent prefix", async () => {
      await page
        .getByTestId("breadcrumb-ipam")
        .getByRole("link", { name: "172.16.0.0/16" })
        .click();

      await expect(page.getByRole("heading", { name: "172.16.0.0/16" })).toBeVisible();
    });
  });
});
