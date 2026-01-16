import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

const GIT_REPO_URL = "https://github.com/opsmill/infrahub-demo-edge.git";
const REPO_NAME = "test repository";

test.describe("Repository - Creation and objects view", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  test.describe.configure({ mode: "serial" });

  const BRANCH_NAME = generateRandomBranchName("repository-branch");

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("Create repository and access objects view", async ({ page }) => {
    await page.goto("/objects/CoreGenericRepository");
    await expect(page.getByRole("link", { name: "demo-edge" })).toBeVisible();
    await page.getByTestId("create-object-button").click();
    await page.getByRole("combobox", { name: "Select an object type" }).click();
    await page.getByRole("option", { name: "Read-Only Repository Core" }).click();
    await page.getByRole("textbox", { name: "Repository location *" }).fill(GIT_REPO_URL);
    await page.getByRole("textbox", { name: "Name *" }).fill(REPO_NAME);
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.getByRole("link", { name: REPO_NAME })).toBeVisible();
    await page.getByRole("link", { name: REPO_NAME }).click();
    await page
      .getByRole("link")
      .filter({ hasNotText: "Group" })
      .filter({ hasText: "Objects" })
      .click();
    await expect(page.getByText("No objects found for this")).toBeVisible();
  });

  test("test", async ({ page }) => {
    await test.step("access repository detailed page", async () => {
      await page.goto("http://localhost:8080/");
      await page.getByRole("button", { name: "Integrations" }).click();
      await page.getByRole("menuitem", { name: "Git Repositories" }).click();
      await expect(page.getByRole("heading", { name: "Git Repository" })).toBeVisible();
      await page.getByRole("link", { name: "test-read-only-repo" }).click();

      await expect(page.getByRole("heading", { name: "test-read-only-repo" })).toBeVisible();
    });

    await test.step("trigger connectivity action", async () => {
      await page.getByTestId("object-details-menu").click();
      await page.getByRole("menuitem", { name: "Check connectivity" }).click();
      await expect(
        page.getByRole("heading", { name: "Check repository connectivity" })
      ).toBeVisible();
      await page.getByRole("button", { name: "Check now" }).click();
      await expect(page.getByText("Successfully accessed")).toBeVisible();
      await page.getByRole("button", { name: "Done" }).click();
    });

    await test.step("trigger latest commit action", async () => {
      await page.getByTestId("object-details-menu").click();
      await page.getByRole("menuitem", { name: "Import latest from remote" }).click();
      await expect(page.getByText("Import from remote started.")).toBeVisible();
    });

    await test.step("trigger current commit from remote action", async () => {
      await page.getByTestId("object-details-menu").click();
      await page.getByRole("menuitem", { name: "Import current commit" }).click();
      await expect(page.getByText("Import of current commit")).toBeVisible();
    });
  });
});
