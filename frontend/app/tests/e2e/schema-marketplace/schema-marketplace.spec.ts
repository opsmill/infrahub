import { expect, type Page, test } from "@playwright/test";

/**
 * Stub responses for the backend /api/marketplace/* endpoints so these tests
 * can run without a reachable Marketplace (and without requiring a live
 * marketplace.infrahub.app). Each test registers the routes it actually
 * depends on; unused routes stay unrouted so failures are loud, not silent.
 */

async function mockStatus(page: Page, overrides: Record<string, unknown> = {}) {
  await page.route("**/api/marketplace/status", async (route) => {
    await route.fulfill({
      json: {
        marketplace_url: "https://marketplace.infrahub.app",
        url_configured: true,
        url_scheme_valid: true,
        upstream_reachable: true,
        checked_at: new Date().toISOString(),
        ...overrides,
      },
    });
  });
}

async function mockEmptyLists(page: Page) {
  await page.route("**/api/marketplace/tags", async (route) => {
    await route.fulfill({ json: { tags: [] } });
  });
  await page.route("**/api/marketplace/schemas**", async (route) => {
    await route.fulfill({
      json: {
        items: [],
        page_info: { has_next_page: false, end_cursor: null },
        total_count: 0,
      },
    });
  });
  await page.route("**/api/marketplace/collections**", async (route) => {
    await route.fulfill({
      json: {
        items: [],
        page_info: { has_next_page: false, end_cursor: null },
        total_count: 0,
      },
    });
  });
}

async function mockOneSchema(page: Page) {
  await page.route("**/api/marketplace/tags", async (route) => {
    await route.fulfill({ json: { tags: [{ id: null, name: "network", count: 1 }] } });
  });
  await page.route("**/api/marketplace/schemas**", async (route) => {
    await route.fulfill({
      json: {
        items: [
          {
            id: "s-1",
            namespace: "infrahub",
            name: "vlan-translation",
            display_name: "VLAN Translation",
            description: "VLAN translation between admin domains.",
            visibility: "public",
            download_count: 2,
            upvote_count: 0,
            fork_count: 0,
            viewer_has_upvoted: false,
            created_at: "2026-04-20T00:00:00Z",
            updated_at: "2026-04-23T00:00:00Z",
            author: { id: "a1", username: "ops", avatar_url: null },
            tags: [{ id: null, name: "network" }],
            latest_version: {
              id: "v1",
              semver: "1.0.0",
              status: "published",
              changelog: null,
              download_count: 0,
              download_url: "/api/v1/schemas/infrahub/vlan-translation/versions/1.0.0/download",
              created_at: "2026-04-20T00:00:00Z",
            },
          },
        ],
        page_info: { has_next_page: false, end_cursor: null },
        total_count: 1,
      },
    });
  });
  await page.route("**/api/marketplace/collections**", async (route) => {
    await route.fulfill({
      json: {
        items: [],
        page_info: { has_next_page: false, end_cursor: null },
        total_count: 0,
      },
    });
  });
}

test.describe("/schema-marketplace", () => {
  test.afterEach(async ({ page }) => {
    await page.unrouteAll({ behavior: "ignoreErrors" });
  });

  test("loads the page and renders a schema card", async ({ page }) => {
    await mockStatus(page);
    await mockOneSchema(page);

    await page.goto("/schema-marketplace");

    await expect(page.getByRole("heading", { name: "Schema Marketplace" })).toBeVisible();
    await expect(page.getByRole("button", { name: /VLAN Translation/ })).toBeVisible();
    await expect(page.getByText("v1.0.0", { exact: false })).toBeVisible();
  });

  test("shows the empty-state message when no schemas match", async ({ page }) => {
    await mockStatus(page);
    await mockEmptyLists(page);

    await page.goto("/schema-marketplace");

    await expect(page.getByText("No schemas match your filters.")).toBeVisible();
  });

  test("flags marketplace misconfiguration when url_scheme_valid is false", async ({ page }) => {
    await mockStatus(page, { marketplace_url: "not-a-url", url_scheme_valid: false });
    await mockEmptyLists(page);

    await page.goto("/schema-marketplace");

    await expect(
      page.getByText("Marketplace is not configured correctly")
    ).toBeVisible();
  });

  test("flags connectivity failure when upstream is unreachable", async ({ page }) => {
    await mockStatus(page, { upstream_reachable: false });
    await mockEmptyLists(page);

    await page.goto("/schema-marketplace");

    await expect(page.getByText("Marketplace is unreachable")).toBeVisible();
  });

  test("selecting a schema enables the install drawer", async ({ page }) => {
    await mockStatus(page);
    await mockOneSchema(page);

    await page.goto("/schema-marketplace");

    const card = page.getByRole("button", { name: /VLAN Translation/ });
    await card.click();
    // "1 selected" appears inside the Install drawer once the schema is
    // picked; before selection it reads "0 selected".
    await expect(page.getByText("1 selected")).toBeVisible();
  });

  test("home-page tile is reachable and links to the marketplace", async ({ page }) => {
    // Don't mock /api/marketplace/* here — the home tile doesn't hit those
    // endpoints; only clicking it should navigate.
    await page.goto("/");
    const tile = page.getByRole("link", { name: /Schema Marketplace/i }).first();
    await expect(tile).toBeVisible();
    await tile.click();
    await expect(page).toHaveURL(/\/schema-marketplace/);
  });
});
