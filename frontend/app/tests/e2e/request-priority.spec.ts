import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../constants";

/**
 * Playwright lowercases request-header names, so the observed key is
 * `x-priority` even though the wire header is title-cased `X-Priority`.
 */
const PRIORITY_HEADER = "x-priority";

type CapturedRequest = {
  url: string;
  method: string;
  priority: string | undefined;
};

/**
 * A frontend-emitted request to the Infrahub API: same origin as the app, on a
 * transport path (`/graphql` or `/api/`). Excludes static assets, the app
 * document, external hosts, and CORS preflights (which never carry the header).
 */
function isInfrahubApiRequest(request: CapturedRequest, appOrigin: string): boolean {
  if (request.method === "OPTIONS") return false;
  const url = new URL(request.url);
  if (url.origin !== appOrigin) return false;
  return url.pathname.startsWith("/graphql") || url.pathname.startsWith("/api/");
}

test.describe("outbound X-Priority header", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test("an interactive flow emits X-Priority: high on every API request", async ({ page }) => {
    const captured: CapturedRequest[] = [];
    page.on("request", (request) => {
      captured.push({
        url: request.url(),
        method: request.method(),
        priority: request.headers()[PRIORITY_HEADER],
      });
    });

    await test.step("drive an interactive navigation", async () => {
      await page.goto("/objects/BuiltinTag");
      await expect(page.getByRole("link", { name: "blue" })).toBeVisible();
    });

    await test.step("assert every Infrahub-API request carried X-Priority: high", async () => {
      const appOrigin = new URL(page.url()).origin;
      const apiRequests = captured.filter((request) => isInfrahubApiRequest(request, appOrigin));

      expect(apiRequests.length).toBeGreaterThan(0);

      for (const request of apiRequests) {
        expect(
          request.priority,
          `${request.method} ${request.url} must carry X-Priority: high`
        ).toBe("high");
      }

      const offenders = apiRequests.filter((request) => request.priority !== "high");
      expect(offenders, "no frontend API request may be normal, low, or unheadered").toEqual([]);
    });
  });
});
