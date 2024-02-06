import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH, ADMIN_CREDENTIALS } from "../constants";

test.describe("/signin", () => {
  test.describe("When is not logged in", () => {
    test("should log in the user", async ({ page }) => {
      await page.goto("/");

      await page.getByRole("link", { name: "Sign in" }).click();
      await expect(page.getByText("Sign in to your account")).toBeVisible();
      await page.getByLabel("Username").fill(ADMIN_CREDENTIALS.username);
      await page.getByLabel("Password").fill(ADMIN_CREDENTIALS.password);
      await page.getByRole("button", { name: "Sign in" }).click();

      await expect(page.getByTestId("current-user-avatar-button")).toBeVisible();
    });

    test("should display an error message when authentication fails", async ({ page }) => {
      await page.goto("/");

      await page.getByRole("link", { name: "Sign in" }).click();
      await expect(page.getByText("Sign in to your account")).toBeVisible();
      await page.getByLabel("Username").fill("wrong username");
      await page.getByLabel("Password").fill("wrong password");
      await page.getByRole("button", { name: "Sign in" }).click();

      await expect(page.locator("#alert-error-sign-in")).toContainText(
        "Invalid username and password"
      );
    });
  });

  test.describe("When logged in", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test("should log out the user", async ({ page }) => {
      await page.goto("/");

      await page.getByTestId("current-user-avatar-button").click();
      await page.getByRole("menuitem", { name: "Sign out" }).click();

      await expect(page.getByRole("link", { name: "Sign in" })).toBeVisible();
    });

    test.fixme("should refresh access token and retry failed request", async ({ page }) => {
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

      const waitForResponse = page.waitForResponse((response) => {
        const reqData = response.request().postDataJSON();
        const status = response.status();

        return reqData?.operationName === "BuiltinTag" && status === 200;
      });
      await page.goto("/objects/BuiltinTag");

      await waitForResponse;

      await expect(page.getByRole("cell", { name: "blue" })).toBeVisible();
    });
  });
});
