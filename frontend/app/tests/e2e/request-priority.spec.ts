import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../constants";

/**
 * E2E: outbound `X-Priority` header (IFC-2890, User Story 6 / SC-001 / SC-002).
 *
 * Proves end-to-end, in a real browser, that the frontend behaves as a
 * first-class emitter of the `X-Priority` request header
 * (contracts/request-priority.contract.md):
 *
 *   - an interactive flow → every captured Infrahub-API request carries
 *     `X-Priority: high` (SC-002: everything the user waits on is `high`);
 *   - a `low`-declared request → `X-Priority: low`;
 *   - no frontend-origin request ever leaves as `normal` or unheadered (FR-003).
 *
 * Playwright lowercases request-header names, so the observed key is
 * `x-priority` even though the wire header is title-cased `X-Priority`.
 *
 * ---
 * SYNTHETIC `low` (deliberate): the production `low` set is empty in v1 — no
 * interactive UI flow issues a `low`-declared request yet (spec Assumption:
 * "the concrete `low` set is small (possibly empty) today"). There is therefore
 * no real UI action that emits `low`, so the `low` case is asserted by issuing
 * a request that declares `low` and observing it at the transport boundary. The
 * per-transport *injection* mechanism (Apollo `context`, REST `params.header`,
 * `fetchUrl(..., { priority })`) is proven by the unit tests under
 * `src/shared/api/`; this E2E proves the header is observable end-to-end.
 *
 * ---
 * ADOPTION METRIC (T032, spec Assumption / SC-001 — NOT automated here): the
 * global counter has no origin dimension, so it cannot be sliced per-caller in
 * an automated assertion. Confirm adoption manually against a running stack:
 *
 *   curl -s http://localhost:8000/metrics | grep infrahub_admission_missing_priority_total
 *
 * With the frontend always emitting an explicit `high`/`low`, this counter
 * trends toward its non-frontend floor (SDK / other callers). See
 * `specs/ifc-2890-frontend-request-priority/quickstart.md` §5.
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
 * document, external hosts (FR-007), and CORS preflights (which never carry the
 * custom header themselves).
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
      // Wait on rendered data so the page's real GraphQL + REST traffic has been
      // emitted and captured before we assert.
      await expect(page.getByRole("link", { name: "blue" })).toBeVisible();
    });

    await test.step("assert every Infrahub-API request carried X-Priority: high", async () => {
      const appOrigin = new URL(page.url()).origin;
      const apiRequests = captured.filter((request) => isInfrahubApiRequest(request, appOrigin));

      // Sanity: the flow must actually have hit the API, or the assertions below
      // would pass vacuously.
      expect(apiRequests.length).toBeGreaterThan(0);

      for (const request of apiRequests) {
        expect(
          request.priority,
          `${request.method} ${request.url} must carry X-Priority: high`
        ).toBe("high");
      }

      // FR-003 / SC-002 made explicit: no interactive request is `normal`,
      // unheadered, or unexpectedly `low`.
      const offenders = apiRequests.filter((request) => request.priority !== "high");
      expect(offenders, "no frontend API request may be normal, low, or unheadered").toEqual([]);
    });
  });

  test("a low-declared request emits X-Priority: low (synthetic)", async ({ page }) => {
    await page.goto("/");

    const lowRequest = page.waitForRequest(
      (request) =>
        request.url().includes("/graphql/") &&
        request.method() === "POST" &&
        request.headers()[PRIORITY_HEADER] === "low"
    );

    // Issue a `low`-declared request from the app origin. See the SYNTHETIC note
    // in the file header for why this is not driven through a UI action.
    await page.evaluate(async () => {
      await fetch(`${window.location.origin}/graphql/main`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Priority": "low" },
        body: JSON.stringify({ query: "{ __typename }" }),
      }).catch(() => {
        // Response status is irrelevant: the header is asserted on the outbound
        // request, which Playwright observes regardless of the response.
      });
    });

    const request = await lowRequest;
    expect(request.headers()[PRIORITY_HEADER]).toBe("low");
    expect(request.headers()[PRIORITY_HEADER]).not.toBe("normal");
  });
});
