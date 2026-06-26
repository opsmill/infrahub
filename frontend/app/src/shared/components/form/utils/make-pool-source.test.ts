import { describe, expect, it } from "vitest";

import { makePoolSource } from "@/shared/components/form/utils/make-pool-source";

import {
  IP_ADDRESS_POOL,
  IP_PREFIX_POOL,
  NUMBER_POOL_KIND,
} from "@/entities/resource-manager/constants";

describe("makePoolSource", () => {
  it("builds an IP address pool source carrying the default prefix length", () => {
    expect(
      makePoolSource({ id: "p1", kind: IP_ADDRESS_POOL, label: "Mgmt", defaultPrefixLength: 16 })
    ).toEqual({
      type: "pool",
      id: "p1",
      kind: IP_ADDRESS_POOL,
      label: "Mgmt",
      defaultPrefixLength: 16,
    });
  });

  it("builds an IP prefix pool source", () => {
    expect(makePoolSource({ id: "p2", kind: IP_PREFIX_POOL, label: "Ext" })).toEqual({
      type: "pool",
      id: "p2",
      kind: IP_PREFIX_POOL,
      label: "Ext",
    });
  });

  it("omits defaultPrefixLength when not provided", () => {
    const source = makePoolSource({ id: "p1", kind: IP_ADDRESS_POOL, label: "Mgmt" });
    expect(source).not.toHaveProperty("defaultPrefixLength");
  });

  it("builds a number pool source without any prefix-length field", () => {
    const source = makePoolSource({
      id: "p3",
      kind: NUMBER_POOL_KIND,
      label: "Numbers",
      // defaultPrefixLength is meaningless for number pools and must be dropped
      defaultPrefixLength: 24,
    });
    expect(source).toEqual({ type: "pool", id: "p3", kind: NUMBER_POOL_KIND, label: "Numbers" });
    expect(source).not.toHaveProperty("defaultPrefixLength");
  });

  it("carries the fromTemplate flag", () => {
    expect(
      makePoolSource({ id: "p1", kind: IP_ADDRESS_POOL, label: "Mgmt", fromTemplate: true })
    ).toMatchObject({ fromTemplate: true });
  });
});
