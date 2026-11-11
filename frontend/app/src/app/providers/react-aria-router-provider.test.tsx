import { Link } from "react-aria-components";
import { afterEach, describe, expect, test } from "vitest";

import { render } from "../../../tests/components/render";
import { ReactAriaRouterProvider } from "./react-aria-router-provider";

const initialUrl = window.location.pathname + window.location.search;

describe("ReactAriaRouterProvider", () => {
  afterEach(() => {
    window.history.replaceState(null, "", initialUrl);
  });

  test("lets the browser open a same-origin absolute link", async () => {
    // GIVEN
    // The link differs from the current URL by its fragment only, so the browser opens it without unloading the test page.
    const absoluteUrl = `${window.location.origin}${initialUrl}#identity-provider`;
    const component = await render(
      <ReactAriaRouterProvider>
        <Link href={absoluteUrl}>Continue with SSO</Link>
      </ReactAriaRouterProvider>
    );

    // WHEN
    await component.getByRole("link", { name: "Continue with SSO" }).click();

    // THEN
    await expect.poll(() => window.location.href).toBe(absoluteUrl);
  });

  test("opens a relative link with the client-side router", async () => {
    // GIVEN
    const component = await render(
      <ReactAriaRouterProvider>
        <Link href="/branches">Branches</Link>
      </ReactAriaRouterProvider>
    );

    // WHEN
    await component.getByRole("link", { name: "Branches" }).click();

    // THEN
    await expect.poll(() => window.location.pathname).toBe("/branches");
  });
});
