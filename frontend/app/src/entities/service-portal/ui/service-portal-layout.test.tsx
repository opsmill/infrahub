import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { graphqlClient } from "@/shared/api/graphql/client";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { render } from "../../../../tests/components/render";
import { ServiceCatalog } from "./service-catalog";
import { ServicePortalLayout } from "./service-portal-layout";

vi.mock("@/shared/api/graphql/client", () => ({
  graphql: (query: string) => query,
  graphqlClient: { query: vi.fn(), mutate: vi.fn() },
}));
vi.mock("@/entities/user-profile/ui/account-menu", () => ({
  AccountMenu: () => <div data-testid="account-menu">Account menu</div>,
}));

describe("ServicePortalLayout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(graphqlClient.query).mockResolvedValue({
      data: { ServiceCatalog: { count: 0, entries: [] } },
    });
  });

  afterEach(() => {
    window.history.replaceState(null, "", "/");
    store.set(datetimeAtom, null);
  });

  test("header has Catalog, Back to Infrahub and the account menu, and no branch selector", async () => {
    window.history.replaceState(null, "", "/service-portal");

    const component = await render(<ServicePortalLayout />);

    await expect
      .element(component.getByRole("link", { name: "Catalog" }))
      .toHaveAttribute("href", "/service-portal");
    await expect
      .element(component.getByRole("link", { name: "Back to Infrahub" }))
      .toHaveAttribute("href", "/");
    await expect.element(component.getByTestId("account-menu")).toBeVisible();
    expect(component.container.querySelector("[data-testid='branch-selector-trigger']")).toBeNull();
    expect(component.container.textContent).not.toMatch(/branch/i);
  });

  test("portal queries use the default branch even when the URL names another branch", async () => {
    window.history.replaceState(
      null,
      "",
      "/service-portal?branch=feature-1&at=2024-01-01T00:00:00Z"
    );
    store.set(datetimeAtom, new Date("2024-01-01T00:00:00Z"));

    const component = await render(
      <ServicePortalLayout>
        <ServiceCatalog />
      </ServicePortalLayout>
    );

    await expect.element(component.getByText("No data")).toBeVisible();
    expect(window.location.search).toBe("");
    expect(store.get(datetimeAtom)).toBeNull();
    expect(graphqlClient.query).toHaveBeenCalled();
    for (const [args] of vi.mocked(graphqlClient.query).mock.calls) {
      expect(args.context?.branch).toBeUndefined();
      expect(args.context?.date).toBeUndefined();
    }
  });
});
