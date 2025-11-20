import { expect, test } from "@playwright/test";

test.describe("when searching an object", () => {
  test("should open search anywhere modal", async ({ page }) => {
    await page.goto("/");

    await test.step("open search anywhere modal with click", async () => {
      await page.getByTestId("search-anywhere-trigger").click();
      await expect(page.getByTestId("search-anywhere")).toBeVisible();
    });

    await test.step("close search anywhere modal with esc key", async () => {
      await page.locator("body").press("Escape");
      await expect(page.getByTestId("search-anywhere")).not.toBeVisible();
    });

    await test.step("open search anywhere modal when using shortcut", async () => {
      await page.keyboard.press("ControlOrMeta+k");
      await expect(page.getByTestId("search-anywhere")).toBeVisible();
    });
  });

  test("displays link to Device list", async ({ page }) => {
    await page.goto("/");

    await test.step("open search anywhere modal with click", async () => {
      await page.getByTestId("search-anywhere-trigger").click();
      await expect(page.getByTestId("search-anywhere")).toBeVisible();
    });

    await test.step("find a matching result", async () => {
      await page.getByTestId("search-anywhere-input").fill("devi");
      await expect(page.getByTestId("search-anywhere")).toContainText("Go to");
      await page.getByRole("option", { name: "Menu Device" }).click();
      await expect(page.getByRole("heading", { name: "Device" })).toBeVisible();
      expect(page.url()).toContain("/objects/InfraDevice");
    });
  });

  test("should display a message when no results found", async ({ page }) => {
    await page.goto("/");

    await test.step("open search anywhere modal", async () => {
      await page.getByTestId("search-anywhere-trigger").click();
      await expect(page.getByTestId("search-anywhere")).toBeVisible();
    });

    await test.step("open search anywhere modal when typing on header input", async () => {
      await page.getByTestId("search-anywhere-input").fill("no_results_query_for_test");
      await expect(
        page
          .getByTestId("search-anywhere")
          .getByRole("option", { name: "Search in docs: no_results_query_for_test" })
      ).toBeVisible();
    });
  });

  test("should display results on search nodes", async ({ page }) => {
    await page.goto("/");

    await test.step("open search anywhere modal", async () => {
      await page.getByTestId("search-anywhere-trigger").click();
      await expect(page.getByTestId("search-anywhere")).toBeVisible();
    });

    await test.step("find a matching result", async () => {
      await page.getByTestId("search-anywhere-input").fill("atl1");
      await expect(
        page.getByTestId("search-anywhere").getByRole("option", { name: "atl1 Location Site" })
      ).toBeVisible();
    });

    await test.step("find a matching IPAM result", async () => {
      await page.getByTestId("search-anywhere-input").fill("10.0");
      await expect(
        page.getByRole("option", { name: "10.0.0.0/8 Ipam IP Prefix IP" })
      ).toBeVisible();
      await expect(
        page.getByRole("option", { name: "10.0.0.0/16 Ipam IP Prefix IP" })
      ).toBeVisible();
      await expect(page.getByText("IP Namespacedefault").first()).toBeVisible();
      await expect(
        page.getByText("IP NamespacedefaultAddress10.0.0.2/32Description-")
      ).toBeVisible();
    });
  });

  test("display result when searching by uuid", async ({ page }) => {
    await page.goto("/objects/InfraAutonomousSystem");

    await page.getByRole("link", { name: "AS174 174" }).click();
    const uuid = (await page.locator("dd").first().textContent()) as string;

    await test.step("open search anywhere modal", async () => {
      await page.getByTestId("search-anywhere-trigger").click();
      await expect(page.getByTestId("search-anywhere")).toBeVisible();
    });

    await page.getByTestId("search-anywhere-input").fill(uuid);
    await expect(
      page.getByRole("option", { name: "AS174 174 Infra Autonomous System" })
    ).toBeVisible();
  });
});
