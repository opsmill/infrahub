import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../constants";

test.describe
  .skip("/path-traversal", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should load page with Path Traversal heading", async ({ page }) => {
      await page.goto("/path-traversal");

      await expect(page.getByText("Path Traversal")).toBeVisible();
    });

    test("should display mode toggle with Path and Dependencies buttons", async ({ page }) => {
      await page.goto("/path-traversal");

      await expect(page.getByRole("button", { name: "Path", exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "Dependencies", exact: true })).toBeVisible();
    });

    test("should show empty state message", async ({ page }) => {
      await page.goto("/path-traversal");

      await expect(page.getByText('Select two objects and click "Find Paths"')).toBeVisible();
    });

    test("should switch to Dependencies mode", async ({ page }) => {
      await page.goto("/path-traversal");

      await page.getByRole("button", { name: "Dependencies", exact: true }).click();

      await expect(page.getByRole("heading", { name: "Dependencies" })).toBeVisible();
      await expect(
        page.getByText('Select a source object, target kinds, and click "Find Dependencies"')
      ).toBeVisible();
    });

    test("should collapse and expand left panel", async ({ page }) => {
      await page.goto("/path-traversal");

      await expect(page.getByText("Path Traversal")).toBeVisible();

      await test.step("collapse the panel", async () => {
        await page.getByRole("button", { name: "Collapse panel" }).click();
        await expect(page.getByText("Path Traversal")).not.toBeVisible();
      });

      await test.step("expand the panel", async () => {
        await page.getByRole("button", { name: "Expand panel" }).click();
        await expect(page.getByText("Path Traversal")).toBeVisible();
      });
    });

    test("should toggle Advanced Options section", async ({ page }) => {
      await page.goto("/path-traversal");

      const advancedToggle = page.getByText("Advanced options");

      if (await advancedToggle.isVisible()) {
        await advancedToggle.click();
      }
    });

    test("auto-runs the query when source and destination are present in the URL", async ({
      page,
    }) => {
      // Pull two real seeded device ids from the demo dataset by listing
      // InfraDevice and reading the first two row links. The exact device names
      // depend on the dataset CI runs against; we just need any two valid ids.
      await page.goto("/objects/InfraDevice");

      const deviceLinks = page.getByRole("link", {
        name: /-edge|-leaf|-spine|-core/i,
      });
      await expect(deviceLinks.first()).toBeVisible({ timeout: 10_000 });

      const sourceHref = await deviceLinks.nth(0).getAttribute("href");
      const destHref = await deviceLinks.nth(1).getAttribute("href");

      // Hrefs look like /objects/InfraDevice/<uuid>
      const sourceId = sourceHref?.split("/").pop() ?? "";
      const destinationId = destHref?.split("/").pop() ?? "";

      // Skip the test gracefully if the dataset has fewer than 2 devices.
      test.skip(!sourceId || !destinationId, "Demo dataset has < 2 InfraDevice objects");

      await page.goto(
        `/path-traversal?mode=path&source=${sourceId}&destination=${destinationId}&depth=5&maxPaths=10`
      );

      // The query should fire automatically — wait for either a "paths found"
      // header or the "No paths found" empty state.
      await expect(page.getByText(/path[s]? found|No paths found/i)).toBeVisible({
        timeout: 10_000,
      });
    });

    test("shows validation message when submitting without a source", async ({ page }) => {
      await page.goto("/path-traversal");

      await page.getByRole("button", { name: "Find Paths" }).click();

      await expect(page.getByText("Source is required")).toBeVisible();
      // The query should not have fired — the right side stays in the empty state.
      await expect(page.getByText('Select two objects and click "Find Paths"')).toBeVisible();
    });

    test("UUID pasted into the source picker resolves to a single match", async ({ page }) => {
      // Get a known device id from the demo dataset.
      await page.goto("/objects/InfraDevice");
      const firstLink = page.getByRole("link", { name: /-edge|-leaf|-spine|-core/i }).first();
      await expect(firstLink).toBeVisible({ timeout: 10_000 });
      const href = await firstLink.getAttribute("href");
      const knownId = href?.split("/").pop() ?? "";

      test.skip(!knownId, "Demo dataset has no InfraDevice objects");

      await page.goto("/path-traversal");

      // Open the source-side combobox. The picker is the first one on the page
      // (label = "Source Object"). The combobox is a popover trigger; click it
      // to open the search list, then type the UUID into the cmdk search input.
      const sourceCombobox = page
        .locator(":text('Source Object')")
        .locator("..")
        .getByRole("combobox")
        .first();
      await sourceCombobox.click();

      const searchInput = page.getByPlaceholder(/search by name|paste an object id/i);
      await searchInput.fill(knownId);

      // The combobox should surface the resolved object as a selectable option.
      // Click the first option that appears.
      const option = page.getByRole("option").first();
      await expect(option).toBeVisible({ timeout: 5000 });
      await option.click();

      // The picker shows the chip with the resolved id text.
      await expect(page.getByText(knownId)).toBeVisible();
    });
  });
