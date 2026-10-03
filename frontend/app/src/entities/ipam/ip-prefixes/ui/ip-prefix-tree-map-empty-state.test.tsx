import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it } from "vitest";

import { IpPrefixTreeMapEmptyState } from "@/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map-empty-state";

import { render } from "../../../../../tests/components/render";

const EXPLANATION = "This prefix holds IP addresses. The tree map shows child prefixes.";

const initialHref = window.location.href;

afterEach(() => {
  window.history.replaceState(null, "", initialHref);
});

describe("IpPrefixTreeMapEmptyState", () => {
  it("shows the utilisation meter, the explanation and the IP Addresses link", async () => {
    // GIVEN
    const utilization = 12;

    // WHEN
    const component = await render(<IpPrefixTreeMapEmptyState utilization={utilization} />);

    // THEN
    await expect
      .element(component.getByRole("meter", { name: "Utilization" }))
      .toHaveAttribute("aria-valuenow", "12");
    await expect.element(component.getByText(EXPLANATION)).toBeVisible();
    await expect
      .element(component.getByRole("link", { name: "IP Addresses" }))
      .toHaveAttribute("href", expect.stringMatching(/\/ip_addresses$/));
  });

  it("shows the explanation and the link without a meter when utilisation is unknown", async () => {
    // GIVEN
    const utilization = null;

    // WHEN
    const component = await render(<IpPrefixTreeMapEmptyState utilization={utilization} />);

    // THEN
    await expect.element(component.getByText(EXPLANATION)).toBeVisible();
    await expect
      .element(component.getByRole("link", { name: "IP Addresses" }))
      .toHaveAttribute("href", expect.stringMatching(/\/ip_addresses$/));
    await expect.element(component.getByRole("meter")).not.toBeInTheDocument();
  });

  it("links to the sibling IP Addresses tab in the current namespace from the tree map route", async () => {
    // GIVEN
    window.history.replaceState(null, "", "/ipam/IpamIPPrefix/prefix-id/tree-map?namespace=abc");

    // WHEN
    const component = await render(
      <Routes>
        <Route path="/ipam/:objectKind/:objectId">
          <Route path="tree-map" element={<IpPrefixTreeMapEmptyState utilization={null} />} />
        </Route>
      </Routes>
    );

    // THEN
    await expect
      .element(component.getByRole("link", { name: "IP Addresses" }))
      .toHaveAttribute("href", "/ipam/IpamIPPrefix/prefix-id/ip_addresses?namespace=abc");
  });
});
