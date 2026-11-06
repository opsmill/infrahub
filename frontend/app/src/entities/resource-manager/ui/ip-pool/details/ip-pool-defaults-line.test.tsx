import { afterEach, describe, expect, it } from "vitest";

import { store } from "@/shared/stores";

import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../tests/components/render";
import {
  generateIpAddressPoolData,
  generateIpPrefixPoolData,
} from "../../../../../../tests/fake/ip-pool";
import { generateNodeSchema } from "../../../../../../tests/fake/schema";
import { IpPoolDefaultsLine } from "./ip-pool-defaults-line";

const initialNodeSchemas = store.get(nodeSchemasAtom);

const prefixSchema = generateNodeSchema({
  kind: "IpamIPPrefix",
  namespace: "Ipam",
  name: "IPPrefix",
  label: "IP Prefix",
});

describe("IpPoolDefaultsLine", () => {
  afterEach(() => {
    store.set(nodeSchemasAtom, initialNodeSchemas);
  });

  it("reads the namespace and the three defaults of a prefix pool", async () => {
    // GIVEN
    const pool = generateIpPrefixPoolData();

    // WHEN
    const component = await render(<IpPoolDefaultsLine pool={pool} poolLabel="IP Prefix Pool" />);

    // THEN
    await expect
      .element(component.baseElement)
      .toMatchTextContent(
        /^IP Prefix Pool in namespace default\s*·\s*Prefix kind defaults to IpamIPPrefix\s*·\s*Prefix length defaults to \/31\s*·\s*Member type defaults to Address$/
      );
  });

  it("lists the namespace and each default of a prefix pool as separate items", async () => {
    // GIVEN
    const pool = generateIpPrefixPoolData();

    // WHEN
    const component = await render(<IpPoolDefaultsLine pool={pool} poolLabel="IP Prefix Pool" />);

    // THEN
    await expect.element(component.getByRole("list")).toBeVisible();
    expect(component.getByRole("listitem").elements()).toHaveLength(4);
  });

  it("reads the namespace and the two defaults of an address pool", async () => {
    // GIVEN
    const pool = generateIpAddressPoolData();

    // WHEN
    const component = await render(<IpPoolDefaultsLine pool={pool} poolLabel="IP Address Pool" />);

    // THEN
    await expect
      .element(component.baseElement)
      .toMatchTextContent(
        /^IP Address Pool in namespace default\s*·\s*Address kind defaults to IpamIPAddress\s*·\s*Prefix length defaults to \/32$/
      );
  });

  it("says a prefix pool has no default for each unset default", async () => {
    // GIVEN
    const pool = generateIpPrefixPoolData({
      default_prefix_type: { value: null },
      default_prefix_length: { value: null },
      default_member_type: { value: null },
    });

    // WHEN
    const component = await render(<IpPoolDefaultsLine pool={pool} poolLabel="IP Prefix Pool" />);

    // THEN
    await expect
      .element(component.baseElement)
      .toMatchTextContent(
        /Prefix kind has no default\s*·\s*Prefix length has no default\s*·\s*Member type has no default$/
      );
  });

  it("says an address pool without a prefix length follows the resource prefix", async () => {
    // GIVEN
    const pool = generateIpAddressPoolData({
      default_address_type: { value: null },
      default_prefix_length: { value: null },
    });

    // WHEN
    const component = await render(<IpPoolDefaultsLine pool={pool} poolLabel="IP Prefix Pool" />);

    // THEN
    await expect
      .element(component.baseElement)
      .toMatchTextContent(
        /Address kind has no default\s*·\s*Prefix length follows the resource prefix$/
      );
  });

  it("opens the schema viewer on the kind when its schema is loaded", async () => {
    // GIVEN
    store.set(nodeSchemasAtom, [prefixSchema]);
    const component = await render(<IpPoolDefaultsLine pool={generateIpPrefixPoolData()} />);

    // WHEN
    await component.getByRole("button", { name: "IpamIPPrefix" }).click();

    // THEN
    await expect.element(component.getByRole("dialog", { name: "Schema viewer" })).toBeVisible();
  });

  it("shows the kind as plain text when its schema is not loaded", async () => {
    // GIVEN
    store.set(nodeSchemasAtom, []);

    // WHEN
    const component = await render(<IpPoolDefaultsLine pool={generateIpPrefixPoolData()} />);

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
    const component = await render(<IpPoolDefaultsLine pool={pool} poolLabel="IP Prefix Pool" />);

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
    const component = await render(<IpPoolDefaultsLine pool={pool} poolLabel="IP Prefix Pool" />);

    // THEN
    await expect
      .element(component.getByRole("link", { name: "lab" }))
      .toHaveAttribute("href", expect.stringContaining("namespace=lab-namespace-id"));
  });
});
