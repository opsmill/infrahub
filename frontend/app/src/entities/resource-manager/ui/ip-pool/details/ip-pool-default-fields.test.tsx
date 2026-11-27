import { afterEach, describe, expect, it } from "vitest";

import { store } from "@/shared/stores";

import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../tests/components/render";
import {
  generateIpAddressPoolData,
  generateIpPrefixPoolData,
} from "../../../../../../tests/fake/ip-pool";
import { generateNodeSchema } from "../../../../../../tests/fake/schema";
import { IpPoolDefaultFields } from "./ip-pool-default-fields";

const initialNodeSchemas = store.get(nodeSchemasAtom);

const prefixSchema = generateNodeSchema({
  kind: "IpamIPPrefix",
  namespace: "Ipam",
  name: "IPPrefix",
  label: "IP Prefix",
});

describe("IpPoolDefaultFields", () => {
  afterEach(() => {
    store.set(nodeSchemasAtom, initialNodeSchemas);
  });

  it("pairs the namespace and each default of a prefix pool with its label", async () => {
    // GIVEN
    const pool = generateIpPrefixPoolData();

    // WHEN
    const component = await render(<IpPoolDefaultFields pool={pool} />);

    // THEN
    expect(
      component
        .getByRole("term")
        .elements()
        .map((term) => term.textContent)
    ).toEqual(["Namespace", "Default prefix kind", "Default prefix length", "Default member type"]);
    expect(
      component
        .getByRole("definition")
        .elements()
        .map((definition) => definition.textContent)
    ).toEqual(["default", "IpamIPPrefix", "/31", "Address"]);
  });

  it("pairs the namespace and each default of an address pool with its label", async () => {
    // GIVEN
    const pool = generateIpAddressPoolData();

    // WHEN
    const component = await render(<IpPoolDefaultFields pool={pool} />);

    // THEN
    expect(
      component
        .getByRole("term")
        .elements()
        .map((term) => term.textContent)
    ).toEqual(["Namespace", "Default address kind", "Default prefix length"]);
    expect(
      component
        .getByRole("definition")
        .elements()
        .map((definition) => definition.textContent)
    ).toEqual(["default", "IpamIPAddress", "/32"]);
  });

  it("shows a dash for each default a prefix pool leaves unset", async () => {
    // GIVEN
    const pool = generateIpPrefixPoolData({
      default_prefix_type: { value: null },
      default_prefix_length: { value: null },
      default_member_type: { value: null },
    });

    // WHEN
    const component = await render(<IpPoolDefaultFields pool={pool} />);

    // THEN
    expect(
      component
        .getByRole("definition")
        .elements()
        .map((definition) => definition.textContent)
    ).toEqual(["default", "-", "-", "-"]);
  });

  it("says the prefix length of an address pool follows the resource prefix when unset", async () => {
    // GIVEN
    const pool = generateIpAddressPoolData({ default_prefix_length: { value: null } });

    // WHEN
    const component = await render(<IpPoolDefaultFields pool={pool} />);

    // THEN
    await expect.element(component.getByText("Follows the resource prefix")).toBeVisible();
  });

  it("keeps the full namespace and kind readable when they are cut off", async () => {
    // GIVEN
    const namespace = "customer-edge-vrf-eu-west-3-production-interconnect";
    const kind = "IpamCustomerProvidedPrefixWithRoutingPolicy";
    const pool = generateIpPrefixPoolData({
      ip_namespace: { id: "long-namespace-id", display_label: namespace, isDefault: false },
      default_prefix_type: { value: kind },
    });

    // WHEN
    const component = await render(<IpPoolDefaultFields pool={pool} />);

    // THEN
    await expect
      .element(component.getByRole("link", { name: namespace }))
      .toHaveAttribute("title", namespace);
    await expect.element(component.getByText(kind, { exact: true })).toHaveAttribute("title", kind);
  });

  it("opens the schema viewer on the kind when its schema is loaded", async () => {
    // GIVEN
    store.set(nodeSchemasAtom, [prefixSchema]);
    const component = await render(<IpPoolDefaultFields pool={generateIpPrefixPoolData()} />);

    // WHEN
    await component.getByRole("button", { name: "IpamIPPrefix" }).click();

    // THEN
    await expect.element(component.getByRole("dialog", { name: "Schema viewer" })).toBeVisible();
  });

  it("shows the kind as plain text when its schema is not loaded", async () => {
    // GIVEN
    store.set(nodeSchemasAtom, []);

    // WHEN
    const component = await render(<IpPoolDefaultFields pool={generateIpPrefixPoolData()} />);

    // THEN
    await expect.element(component.getByText("IpamIPPrefix", { exact: true })).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "IpamIPPrefix" }))
      .not.toBeInTheDocument();
  });

  it("links the default namespace to the unfiltered IPAM page", async () => {
    // GIVEN
    const pool = generateIpPrefixPoolData();

    // WHEN
    const component = await render(<IpPoolDefaultFields pool={pool} />);

    // THEN
    await expect
      .element(component.getByRole("link", { name: "default" }))
      .toHaveAttribute("href", "/ipam");
  });

  it("links another namespace to the IPAM page filtered on it", async () => {
    // GIVEN
    const pool = generateIpPrefixPoolData({
      ip_namespace: { id: "lab-namespace-id", display_label: "lab", isDefault: false },
    });

    // WHEN
    const component = await render(<IpPoolDefaultFields pool={pool} />);

    // THEN
    await expect
      .element(component.getByRole("link", { name: "lab" }))
      .toHaveAttribute("href", expect.stringContaining("namespace=lab-namespace-id"));
  });
});
