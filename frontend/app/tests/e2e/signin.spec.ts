import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH, ADMIN_CREDENTIALS } from "../constants";

test.describe("/signin", () => {
  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test.describe("When is not logged in", () => {
    test("should log in the user", async ({ page }) => {
      await page.goto("/");

      await page.getByRole("link", { name: "Log in anonymous" }).click();

      await expect(page.getByText("Sign in to your account")).toBeVisible();
      await page.getByLabel("Username").fill(ADMIN_CREDENTIALS.username);
      await page.getByLabel("Password").fill(ADMIN_CREDENTIALS.password);
      await page.getByRole("button", { name: "Sign in" }).click();

      await expect(page.getByTestId("authenticated-menu-trigger")).toBeVisible();
    });

    test("should display an error message when authentication fails", async ({ page }) => {
      await page.goto("/");

      await page.getByRole("link", { name: "Log in anonymous" }).click();

      await expect(page.getByText("Sign in to your account")).toBeVisible();
      await page.getByLabel("Username").fill("wrong username");
      await page.getByLabel("Password").fill("wrong password");
      await page.getByRole("button", { name: "Sign in" }).click();

      await expect(page.locator("#alert-error-sign-in")).toContainText(
        "Invalid username and password"
      );
    });

    test("should redirect to the initial page after login", async ({ page }) => {
      const date = encodeURIComponent(new Date().toISOString());
      const initialPage = `/objects/BuiltinTag?branch=atl1-delete-upstream&at=${date}`;
      await page.goto(initialPage);

      await page.getByRole("link", { name: "Log in anonymous" }).click();

      await expect(page.getByText("Sign in to your account")).toBeVisible();
      await page.getByLabel("Username").fill(ADMIN_CREDENTIALS.username);
      await page.getByLabel("Password").fill(ADMIN_CREDENTIALS.password);
      await page.getByRole("button", { name: "Sign in" }).click();

      await expect(page.getByTestId("authenticated-menu-trigger")).toBeVisible();
      await expect(page.url()).toContain(initialPage);
    });
  });

  test.describe("When logged in", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should log out the user", async ({ page }) => {
      await page.goto("/");

      await page.getByTestId("authenticated-menu-trigger").click();
      await page.getByRole("menuitem", { name: "Logout" }).click();

      await expect(page.getByRole("link", { name: "Log in anonymous" })).toBeVisible();
    });

    test("redirect to homepage if user is already logged in", async ({ page }) => {
      await page.goto("/signin");

      await expect(page.getByText("Welcome to Infrahub!")).toBeVisible();
    });

    test("should refresh access token and retry failed request", async ({ page }) => {
      let blockRequest = true; // force 401 on first call

      await page.route("**/graphql/main**", async (route) => {
        const reqData = route.request().postDataJSON();

        if (reqData.operationName === "BuiltinTag" && blockRequest) {
          blockRequest = false;

          await route.fulfill({
            status: 401,
            json: {
              data: null,
              errors: [
                {
                  message: "Expired Signature",
                  extensions: {
                    code: 401,
                  },
                },
              ],
            },
          });
        } else {
          await route.fallback();
        }
      });

      await page.goto("/objects/BuiltinTag");

      await expect(page.getByRole("cell", { name: "blue" })).toBeVisible();
    });
  });
});
