import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { render } from "../../../../tests/components/render";
import { ACCESS_TOKEN_KEY } from "../constants";
import { AuthProvider, useAuth } from "./useAuth";

// Tiny probe component: renders the current auth state so the test can
// observe AuthProvider's reaction to `storage` events without poking at
// React internals.
function AuthProbe() {
  const { accessToken, isAuthenticated } = useAuth();
  return (
    <div>
      <span data-testid="token">{accessToken ?? ""}</span>
      <span data-testid="status">{isAuthenticated ? "auth" : "anon"}</span>
    </div>
  );
}

describe("AuthProvider — cross-tab storage reconciliation", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("seeds state from localStorage on mount", async () => {
    // GIVEN a populated access token before the provider mounts (mirrors
    // a page load after the user is already signed in)
    localStorage.setItem(ACCESS_TOKEN_KEY, "seeded-token");

    // WHEN the provider mounts
    const component = await render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    );

    // THEN it picks up the existing token without waiting for a write
    await expect.element(component.getByTestId("token")).toHaveTextContent("seeded-token");
    await expect.element(component.getByTestId("status")).toHaveTextContent("auth");
  });

  it("logs the user out when another tab clears the access token", async () => {
    // GIVEN this tab is authenticated
    localStorage.setItem(ACCESS_TOKEN_KEY, "tab-A-token");
    const component = await render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    );
    await expect.element(component.getByTestId("status")).toHaveTextContent("auth");

    // WHEN another tab logs out — simulated by clearing storage and
    // dispatching the same StorageEvent the browser would emit cross-tab
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    window.dispatchEvent(
      new StorageEvent("storage", {
        key: ACCESS_TOKEN_KEY,
        oldValue: "tab-A-token",
        newValue: null,
      })
    );

    // THEN this tab follows: state flips to unauthenticated
    await expect.element(component.getByTestId("status")).toHaveTextContent("anon");
    await expect.element(component.getByTestId("token")).toHaveTextContent("");
  });

  it("ignores storage events for unrelated keys", async () => {
    // GIVEN this tab is authenticated
    localStorage.setItem(ACCESS_TOKEN_KEY, "still-good");
    const component = await render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    );
    await expect.element(component.getByTestId("status")).toHaveTextContent("auth");

    // WHEN a storage event fires for something else (e.g. sidebar collapse,
    // which also uses localStorage)
    window.dispatchEvent(
      new StorageEvent("storage", {
        key: "sidebar:collapsed",
        oldValue: "false",
        newValue: "true",
      })
    );

    // THEN our auth state is undisturbed
    await expect.element(component.getByTestId("status")).toHaveTextContent("auth");
    await expect.element(component.getByTestId("token")).toHaveTextContent("still-good");
  });
});
