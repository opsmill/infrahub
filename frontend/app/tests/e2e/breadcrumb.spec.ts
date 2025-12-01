import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../constants";

test.describe("Breadcrumb Navigation", () => {
  test.describe("/activities - Activities breadcrumb", () => {
    test("should display breadcrumb on activities page", async ({ page }) => {
      await page.goto("/activities");

      const breadcrumb = page.getByTestId("breadcrumb-activities");
      await expect(breadcrumb.getByRole("link", { name: "Activities" })).toBeVisible();
    });
  });

  test.describe("/branches - Branches breadcrumb", () => {
    test("should display breadcrumb on branches list page", async ({ page }) => {
      await page.goto("/branches");

      const breadcrumb = page.getByTestId("breadcrumb-branches");
      await expect(breadcrumb).toBeVisible();
      await expect(breadcrumb.getByRole("link", { name: "Branches" })).toBeVisible();
    });

    test("should display branch name in breadcrumb on branch details page", async ({ page }) => {
      await page.goto("/branches/main");

      const breadcrumb = page.getByTestId("breadcrumb-branches");
      await expect(breadcrumb).toBeVisible();
      await expect(breadcrumb.getByRole("link", { name: "Branches" })).toBeVisible();
      await breadcrumb.getByRole("button", { name: "main" }).click();
      await page.getByRole("option", { name: "atl1-delete-upstream" }).click();
      await expect(page).toHaveURL(/\/branches\/atl1-delete-upstream$/);
    });

    test("should navigate back to branches list when clicking Branches breadcrumb", async ({
      page,
    }) => {
      await page.goto("/branches/main");

      await page.getByTestId("breadcrumb-branches").getByRole("link", { name: "Branches" }).click();
      await expect(page).toHaveURL(/\/branches$/);
    });
  });

  test.describe("/graphql - GraphQL breadcrumb", () => {
    test("should display breadcrumb on GraphQL sandbox page", async ({ page }) => {
      await page.goto("/graphql");

      const breadcrumb = page.getByTestId("breadcrumb-graphql");
      await expect(breadcrumb.getByRole("link", { name: "GraphQL Sandbox" })).toBeVisible();
    });
  });

  test.describe("/ipam - IPAM breadcrumb", () => {
    test("should display breadcrumb on IPAM page", async ({ page }) => {
      await page.goto("/ipam");

      const breadcrumb = page.getByTestId("breadcrumb-ipam");
      await expect(breadcrumb.getByRole("link", { name: "IP Address Manager" })).toBeVisible();

      await page.getByRole("link", { name: "10.1.0.0/31" }).click();
      await expect(page.getByRole("heading", { name: "10.1.0.0/31" })).toBeVisible();

      await expect(breadcrumb.getByRole("link", { name: "IP Address Manager" })).toBeVisible();
      await expect(breadcrumb.getByRole("link", { name: "10.0.0.0/8" })).toBeVisible();
      await expect(breadcrumb.getByRole("link", { name: "10.1.0.0/16" })).toBeVisible();
      await expect(breadcrumb.getByRole("link", { name: "10.1.0.0/31" })).toBeVisible();
    });
  });

  test.describe("/objects - Objects breadcrumb", () => {
    test("should display object kind in breadcrumb on objects list page", async ({ page }) => {
      await page.goto("/objects/InfraDevice");
      const breadcrumb = page.getByTestId("breadcrumb-navigation");
      await expect(breadcrumb.getByRole("link", { name: "Device" })).toBeVisible();

      await page.getByRole("link", { name: "atl1-core1" }).click();

      await expect(breadcrumb.getByRole("link", { name: "Device" })).toBeVisible();
      await expect(breadcrumb.getByRole("link", { name: "atl1-core1" })).toBeVisible();

      await breadcrumb.getByRole("button", { name: "Select a different Device" }).click();
      await page.getByRole("option", { name: "atl1-core2" }).click();

      await expect(breadcrumb.getByRole("link", { name: "atl1-core2" })).toBeVisible();
      await expect(page.getByTestId("object-header").getByText("atl1-core2")).toBeVisible();
    });
  });

  test.describe("/profile - Account Profile breadcrumb", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should display breadcrumb on profile page", async ({ page }) => {
      await page.goto("/profile");

      const breadcrumb = page.getByTestId("breadcrumb-profile");
      await expect(breadcrumb.getByText("Account settings")).toBeVisible();
    });
  });

  test.describe("/proposed-changes - Proposed Changes breadcrumb", () => {
    test("should display breadcrumb on proposed changes list page", async ({ page }) => {
      await page.goto("/proposed-changes");

      const breadcrumb = page.getByTestId("breadcrumb-proposed-changes");
      await expect(breadcrumb.getByRole("link", { name: "Proposed changes" })).toBeVisible();
    });

    test.describe("when logged in as Admin", () => {
      test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

      test("should display 'new' in breadcrumb on proposed change creation page", async ({
        page,
      }) => {
        await page.goto("/proposed-changes/new");

        const breadcrumb = page.getByTestId("breadcrumb-proposed-changes");
        await expect(breadcrumb.getByRole("link", { name: "Proposed changes" })).toBeVisible();
        await expect(breadcrumb.getByRole("link", { name: "new" })).toBeVisible();
      });
    });
  });

  test.describe("/tasks - Tasks breadcrumb", () => {
    test("should display breadcrumb on tasks page", async ({ page }) => {
      await page.goto("/tasks");

      const breadcrumb = page.getByTestId("breadcrumb-tasks");
      await expect(breadcrumb.getByText("Tasks")).toBeVisible();
    });
  });

  test.describe("/resource-manager - Resource Manager breadcrumb", () => {
    test("should display breadcrumb on resource manager page", async ({ page }) => {
      await page.goto("/resource-manager");

      const breadcrumb = page.getByTestId("breadcrumb-navigation");
      await expect(breadcrumb.getByRole("link", { name: "Resource manager" })).toBeVisible();

      await page.getByRole("link", { name: "External prefixes pool" }).click();
      await expect(page.getByRole("link", { name: "IP Prefix Pool" })).toBeVisible();
      await expect(page.getByRole("link", { name: "External prefixes pool" })).toBeVisible();

      await page.getByRole("link", { name: "View", exact: true }).click();
      await expect(
        page
          .getByTestId("breadcrumb-resource-manager")
          .getByRole("link", { name: "203.111.0.0/16" })
      ).toBeVisible();
    });
  });

  test.describe("/role-management - Role Management breadcrumb", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should display breadcrumb on role management accounts page", async ({ page }) => {
      await page.goto("/role-management");

      const breadcrumb = page.getByTestId("breadcrumb-role-management");
      await expect(breadcrumb.getByRole("link", { name: "Users & Permissions" })).toBeVisible();
      await expect(breadcrumb.getByRole("link", { name: "Accounts" })).toBeVisible();
    });

    test("should display breadcrumb on role management groups page", async ({ page }) => {
      await page.goto("/role-management/groups");

      const breadcrumb = page.getByTestId("breadcrumb-role-management");
      await expect(breadcrumb.getByRole("link", { name: "Users & Permissions" })).toBeVisible();
      await expect(breadcrumb.getByRole("link", { name: "Groups" })).toBeVisible();
    });

    test("should display breadcrumb on role management roles page", async ({ page }) => {
      await page.goto("/role-management/roles");

      const breadcrumb = page.getByTestId("breadcrumb-role-management");
      await expect(breadcrumb.getByRole("link", { name: "Users & Permissions" })).toBeVisible();
      await expect(breadcrumb.getByRole("link", { name: "Roles" })).toBeVisible();
    });

    test("should display breadcrumb on role management global permissions page", async ({
      page,
    }) => {
      await page.goto("/role-management/global-permissions");

      const breadcrumb = page.getByTestId("breadcrumb-role-management");
      await expect(breadcrumb.getByRole("link", { name: "Users & Permissions" })).toBeVisible();
      await expect(breadcrumb.getByRole("link", { name: "Global Permissions" })).toBeVisible();
    });

    test("should display breadcrumb on role management object permissions page", async ({
      page,
    }) => {
      await page.goto("/role-management/object-permissions");

      const breadcrumb = page.getByTestId("breadcrumb-role-management");
      await expect(breadcrumb.getByRole("link", { name: "Users & Permissions" })).toBeVisible();
      await expect(breadcrumb.getByRole("link", { name: "Object Permissions" })).toBeVisible();
    });
  });

  test.describe("/schema - Schema Viewer breadcrumb", () => {
    test("should display breadcrumb on schema page", async ({ page }) => {
      await page.goto("/schema");

      const breadcrumb = page.getByTestId("breadcrumb-schema");
      await expect(breadcrumb.getByText("Schema")).toBeVisible();
    });
  });
});
