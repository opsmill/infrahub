import { describe, expect, it } from "vitest";

import { generateIpPoolResource } from "../../../../../tests/fake/ip-pool";
import { sortIpPoolResourcesByFillOrder } from "./sort-ip-pool-resources-by-fill-order";

const resource = (display_label: string, allocationWeight: number | null) =>
  generateIpPoolResource({ id: display_label, display_label, allocationWeight });

describe("sortIpPoolResourcesByFillOrder", () => {
  it("orders by weight, highest first, then by prefix", () => {
    // GIVEN
    const resources = [
      resource("10.10.8.0/23", 50),
      resource("10.10.4.0/22", 100),
      resource("10.10.0.0/22", 100),
    ];

    // WHEN
    const sorted = sortIpPoolResourcesByFillOrder(resources);

    // THEN
    expect(sorted.map(({ display_label }) => display_label)).toEqual([
      "10.10.0.0/22",
      "10.10.4.0/22",
      "10.10.8.0/23",
    ]);
  });

  it("orders prefixes without a weight by their numbers, not their characters", () => {
    // GIVEN
    const resources = [resource("10.10.0.0/22", null), resource("10.2.0.0/16", null)];

    // WHEN
    const sorted = sortIpPoolResourcesByFillOrder(resources);

    // THEN
    expect(sorted.map(({ display_label }) => display_label)).toEqual([
      "10.2.0.0/16",
      "10.10.0.0/22",
    ]);
  });

  it("orders IPv6 prefixes by their hexadecimal value", () => {
    // GIVEN
    const resources = [resource("2001:db8:10::/48", null), resource("2001:db8:a::/48", null)];

    // WHEN
    const sorted = sortIpPoolResourcesByFillOrder(resources);

    // THEN
    expect(sorted.map(({ display_label }) => display_label)).toEqual([
      "2001:db8:a::/48",
      "2001:db8:10::/48",
    ]);
  });

  it("orders IPv4 prefixes before IPv6 prefixes", () => {
    // GIVEN
    const resources = [resource("::/0", null), resource("255.0.0.0/8", null)];

    // WHEN
    const sorted = sortIpPoolResourcesByFillOrder(resources);

    // THEN
    expect(sorted.map(({ display_label }) => display_label)).toEqual(["255.0.0.0/8", "::/0"]);
  });

  it("orders prefixes with the same network address by length, shortest first", () => {
    // GIVEN
    const resources = [resource("10.0.0.0/24", null), resource("10.0.0.0/16", null)];

    // WHEN
    const sorted = sortIpPoolResourcesByFillOrder(resources);

    // THEN
    expect(sorted.map(({ display_label }) => display_label)).toEqual([
      "10.0.0.0/16",
      "10.0.0.0/24",
    ]);
  });

  it("puts a resource prefix without a weight after the weighted ones", () => {
    // GIVEN
    const resources = [resource("10.0.0.0/8", null), resource("172.16.0.0/12", 1)];

    // WHEN
    const sorted = sortIpPoolResourcesByFillOrder(resources);

    // THEN
    expect(sorted.map(({ display_label }) => display_label)).toEqual([
      "172.16.0.0/12",
      "10.0.0.0/8",
    ]);
    expect(resources[0]?.display_label).toBe("10.0.0.0/8");
  });
});
