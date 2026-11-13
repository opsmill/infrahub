import { describe, expect, it } from "vitest";

import type {
  IpAddressPoolNode,
  IpPrefixPoolNode,
} from "@/entities/resource-manager/api/get-ip-pool-from-api";

import { mapToIpAddressPoolData, mapToIpPrefixPoolData } from "./ip-pool.mappers";

const namespace = { id: "ns-id", display_label: "default", default: { value: true } };

describe("mapToIpPrefixPoolData", () => {
  it("maps the defaults and the namespace of a prefix pool", () => {
    // GIVEN
    const node = {
      id: "pool-id",
      hfid: ["Links"],
      display_label: "Links",
      __typename: "CoreIPPrefixPool",
      name: { value: "Links" },
      description: { value: "" },
      default_prefix_length: { value: 31 },
      default_prefix_type: { value: "IpamIPPrefix" },
      default_member_type: { value: "address" },
      ip_namespace: { node: namespace },
    } as unknown as IpPrefixPoolNode;

    // WHEN
    const pool = mapToIpPrefixPoolData(node);

    // THEN
    expect(pool).toEqual({
      id: "pool-id",
      hfid: ["Links"],
      display_label: "Links",
      __typename: "CoreIPPrefixPool",
      name: { value: "Links" },
      description: { value: null },
      default_prefix_length: { value: 31 },
      default_prefix_type: { value: "IpamIPPrefix" },
      default_member_type: { value: "address" },
      ip_namespace: { id: "ns-id", display_label: "default", isDefault: true },
    });
  });

  it("keeps an unset default empty and a namespace without the default flag as not default", () => {
    // GIVEN
    const node = {
      id: "pool-id",
      name: { value: "Links" },
      description: { value: null },
      default_prefix_length: { value: null },
      default_prefix_type: { value: null },
      default_member_type: { value: null },
      ip_namespace: { node: { id: "ns-id", display_label: "customer-blue" } },
    } as unknown as IpPrefixPoolNode;

    // WHEN
    const pool = mapToIpPrefixPoolData(node);

    // THEN
    expect(pool.default_prefix_length.value).toBeNull();
    expect(pool.default_prefix_type.value).toBeNull();
    expect(pool.default_member_type.value).toBeNull();
    expect(pool.ip_namespace).toEqual({
      id: "ns-id",
      display_label: "customer-blue",
      isDefault: false,
    });
  });
});

describe("mapToIpAddressPoolData", () => {
  it("maps the address kind and the prefix length of an address pool", () => {
    // GIVEN
    const node = {
      id: "pool-id",
      hfid: ["Loopbacks"],
      display_label: "Loopbacks",
      __typename: "CoreIPAddressPool",
      name: { value: "Loopbacks" },
      description: { value: null },
      default_prefix_length: { value: 32 },
      default_address_type: { value: "IpamIPAddress" },
      ip_namespace: { node: namespace },
    } as unknown as IpAddressPoolNode;

    // WHEN
    const pool = mapToIpAddressPoolData(node);

    // THEN
    expect(pool.__typename).toBe("CoreIPAddressPool");
    expect(pool.default_address_type).toEqual({ value: "IpamIPAddress" });
    expect(pool.default_prefix_length).toEqual({ value: 32 });
  });
});
