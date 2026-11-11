import { Link } from "react-aria-components";
import { afterEach, describe, expect, test, vi } from "vitest";

import { render } from "../../../tests/components/render";
import { ReactAriaRouterProvider } from "./react-aria-router-provider";

const initialUrl = window.location.pathname + window.location.search;

describe("ReactAriaRouterProvider", () => {
  afterEach(() => {
    window.history.replaceState(null, "", initialUrl);
  });

  test("loads a same-origin absolute link as a full page", async () => {
    // GIVEN
    // Only a link on the test page's own origin is handed to the provider.
    const authorizeUrl = `${window.location.origin}/api/oidc/provider1/authorize?final_url=%2F`;
    const loadPage = vi.fn();
    const component = await render(
      <ReactAriaRouterProvider loadPage={loadPage}>
        <Link href={authorizeUrl}>Continue with SSO</Link>
      </ReactAriaRouterProvider>
    );

    // WHEN
    await component.getByRole("link", { name: "Continue with SSO" }).click();

    // THEN
    expect(loadPage).toHaveBeenCalledExactlyOnceWith(authorizeUrl);
    expect(window.location.pathname + window.location.search).toBe(initialUrl);
  });

  test("opens a relative link with the client-side router", async () => {
    // GIVEN
    const loadPage = vi.fn();
    const component = await render(
      <ReactAriaRouterProvider loadPage={loadPage}>
        <Link href="/branches">Branches</Link>
      </ReactAriaRouterProvider>
    );

    // WHEN
    await component.getByRole("link", { name: "Branches" }).click();

    // THEN
    await expect.poll(() => window.location.pathname).toBe("/branches");
    expect(loadPage).not.toHaveBeenCalled();
  });
});
