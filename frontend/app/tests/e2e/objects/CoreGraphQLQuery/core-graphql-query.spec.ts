import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../../constants";

test.describe("/objects/CoreGraphQLQuery/:graphqlQueryId - GraphQL Query details page", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("should create a new graphql successfully", async ({ page }) => {
    await test.step("Navigate to CoreGraphQLQuery page", async () => {
      await page.goto("/objects/CoreGraphQLQuery");
      await expect(page.getByRole("heading", { name: "GraphQL Query" })).toBeVisible();
      await expect(page.getByText("Just a moment")).not.toBeVisible();
    });

    await test.step("Create a new graphql query", async () => {
      await page.getByTestId("create-object-button").click();
      await page.getByLabel("Name *").fill("test-graphql-query");

      await page
        .getByTestId("codemirror-editor")
        .getByRole("textbox")
        .fill(
          `query GET_TAGS {
        ProfileBuiltinTag {
          edges {
            node {
              id
              display_label
              description {
                id
                value
              }
            }
          }
        }
      }`
        );

      await page.getByLabel("Description").click();
      await page.getByLabel("Description").fill("A profile for E2E test");

      await page.getByRole("button", { name: "Save" }).click();
    });

    await test.step("Verify graphql query creation success", async () => {
      await expect(page.getByText("GraphQLQuery created")).toBeVisible();
      await expect(page.getByRole("link", { name: "test-graphql-query" })).toBeVisible();
    });
  });

  test("access the created graphql query, view its data, and edit it", async ({ page }) => {
    await test.step("Navigate to CoreGraphQLQuery page", async () => {
      await page.goto("/objects/CoreGraphQLQuery");
      await page.getByRole("link", { name: "test-graphql-query" }).click();
    });

    await expect(
      page.getByText("DescriptionA profile for E2E test ", { exact: true })
    ).toBeVisible();
    await expect(page.getByText("query GET_TAGS {")).toBeVisible();

    await page.getByTestId("edit-button").click();
    await page.getByLabel("Description").fill("A profile for E2E test updated");
    await page.getByRole("button", { name: "Save" }).click();

    await expect(page.getByText("GraphQLQuery updated")).toBeVisible();
    await expect(
      page.getByText("DescriptionA profile for E2E test updated", { exact: true })
    ).toBeVisible();

    await page
      .getByRole("cell", { name: "test-graphql-query" })
      .getByTestId("view-metadata-button")
      .click();
    await page.getByTestId("properties-edit-button").click();
    await page.getByLabel("is protected *").check();
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.getByText("Metadata updated")).toBeVisible();

    await test.step("return to list using breadcrumb", async () => {
      await page
        .getByTestId("breadcrumb-navigation")
        .getByRole("link", { name: "GraphQL Query" })
        .click();
      expect(page.url()).toContain("/objects/CoreGraphQLQuery");
    });
  });

  test("delete a graphql query", async ({ page }) => {
    await page.goto("/objects/CoreGraphQLQuery");

    await test.step("Delete the profile", async () => {
      await page
        .getByRole("row", { name: "test-graphql-query" })
        .getByTestId("delete-row-button")
        .click();
      await page.getByTestId("modal-delete-confirm").click();
    });

    await expect(page.getByText("Object test-graphql-query deleted")).toBeVisible();
  });
});
