import { Page, expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH, ADMIN_CREDENTIALS } from "../constants";

const disableSSO = async (page: Page) => {
  return page.route("*/**/api/config", async (route) => {
    const response = await route.fetch();
    const json = await response.json();
    await route.fulfill({
      json: {
        ...json,
        sso: {
          providers: [],
          enabled: false,
        },
      },
    });
  });
};

const enableSSO = async (page: Page) => {
  return page.route("*/**/api/config", async (route) => {
    const response = await route.fetch();
    const json = await response.json();
    await route.fulfill({
      json: {
        ...json,
        sso: {
          providers: [
            {
              name: "google",
              display_label: "Google",
              icon: "mdi:google",
              protocol: "oauth2",
              authorize_path: "/api/oauth2/google/authorize",
              token_path: "/api/oauth2/google/token",
            },
          ],
          enabled: true,
        },
      },
    });
  });
};

test.describe("/login", () => {
  test.beforeEach(async function ({ page }) {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test.describe("When is not logged in", () => {
    test.describe("when SSO is enabled", () => {
      test("should display log in using SSO", async ({ page }) => {
        await enableSSO(page);
        await page.goto("/login");

        await test.step("should display Google SSO button", async () => {
          await expect(page.getByRole("link", { name: "Continue with Google" })).toBeVisible();
        });

        await test.step("should display username and password fields", async () => {
          await page.getByRole("button", { name: "Log in with your credentials" }).click();
          await expect(page.getByLabel("Username")).toBeVisible();
          await expect(page.getByLabel("Password")).toBeVisible();
        });

        await test.step("go back to log in with SSO", async () => {
          await page.getByRole("button", { name: "Log in with SSO" }).click();
          await expect(page.getByRole("link", { name: "Continue with Google" })).toBeVisible();
        });
      });
    });

    test("should log in the user", async ({ page }) => {
      await disableSSO(page);
      await page.goto("/");

      await page.getByRole("link", { name: "Log in anonymous" }).click();

      await expect(page.getByText("Log in to your account")).toBeVisible();
      await page.getByLabel("Username").fill(ADMIN_CREDENTIALS.username);
      await page.getByLabel("Password").fill(ADMIN_CREDENTIALS.password);
      await page.getByRole("button", { name: "Log in" }).click();

      await expect(page.getByTestId("authenticated-menu-trigger")).toBeVisible();
    });

    test("should display an error message when authentication fails", async ({ page }) => {
      await disableSSO(page);
      await page.goto("/");

      await page.getByRole("link", { name: "Log in anonymous" }).click();

      await expect(page.getByText("Log in to your account")).toBeVisible();
      await page.getByLabel("Username").fill("wrong username");
      await page.getByLabel("Password").fill("wrong password");
      await page.getByRole("button", { name: "Log in" }).click();

      await expect(page.locator("#alert-error-sign-in")).toContainText(
        "Invalid username and password"
      );
    });

    test("should redirect to the initial page after login", async ({ page }) => {
      await disableSSO(page);
      const date = encodeURIComponent(new Date().toISOString());
      const initialPage = `/objects/BuiltinTag?branch=atl1-delete-upstream&at=${date}`;
      await page.goto(initialPage);

      await page.getByRole("link", { name: "Log in anonymous" }).click();

      await expect(page.getByText("Log in to your account")).toBeVisible();
      await page.getByLabel("Username").fill(ADMIN_CREDENTIALS.username);
      await page.getByLabel("Password").fill(ADMIN_CREDENTIALS.password);
      await page.getByRole("button", { name: "Log in" }).click();

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
      await page.goto("/login");

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
