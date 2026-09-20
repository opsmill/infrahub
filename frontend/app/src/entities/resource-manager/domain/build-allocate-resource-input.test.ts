import { describe, expect, it } from "vitest";

import { buildAllocateResourceInput } from "@/entities/resource-manager/domain/build-allocate-resource-input";
import { IP_ADDRESS_POOL, IP_PREFIX_POOL } from "@/entities/resource-manager/domain/model/pool";

describe("buildAllocateResourceInput", () => {
  it("wraps the pool id and node data, with no prefix_length when none was entered", () => {
    const input = buildAllocateResourceInput({
      poolId: "pool-1",
      poolFieldValue: { from_pool: { id: "pool-1" } },
      nodeData: { description: { value: "from pool" } },
    });

    expect(input).toEqual({ id: "pool-1", data: { description: { value: "from pool" } } });
    expect(input).not.toHaveProperty("prefix_length");
  });

  it("includes prefix_length when the field carries a user-entered prefix length", () => {
    const input = buildAllocateResourceInput({
      poolId: "pool-1",
      poolFieldValue: { from_pool: { id: "pool-1", prefixLength: 24 } },
      nodeData: {},
    });

    expect(input).toEqual({ id: "pool-1", data: {}, prefix_length: 24 });
  });

  it("omits prefix_length for a non from-pool value", () => {
    const input = buildAllocateResourceInput({
      poolId: "pool-1",
      poolFieldValue: null,
      nodeData: { description: { value: "x" } },
    });

    expect(input).toEqual({ id: "pool-1", data: { description: { value: "x" } } });
  });

  it("maps the allocated kind to address_type for an IP address pool", () => {
    const input = buildAllocateResourceInput({
      poolId: "pool-1",
      poolKind: IP_ADDRESS_POOL,
      poolFieldValue: { from_pool: { id: "pool-1", allocatedKind: "IpamIPAddress" } },
      nodeData: {},
    });

    expect(input).toEqual({ id: "pool-1", data: {}, address_type: "IpamIPAddress" });
  });

  it("maps the allocated kind to prefix_type for an IP prefix pool", () => {
    const input = buildAllocateResourceInput({
      poolId: "pool-1",
      poolKind: IP_PREFIX_POOL,
      poolFieldValue: {
        from_pool: { id: "pool-1", allocatedKind: "IpamIPPrefix", prefixLength: 26 },
      },
      nodeData: {},
    });

    expect(input).toEqual({
      id: "pool-1",
      data: {},
      prefix_length: 26,
      prefix_type: "IpamIPPrefix",
    });
  });

  it("defaults the allocated kind to address_type when the pool kind is unknown", () => {
    const input = buildAllocateResourceInput({
      poolId: "pool-1",
      poolFieldValue: { from_pool: { id: "pool-1", allocatedKind: "IpamIPAddress" } },
      nodeData: {},
    });

    expect(input).toEqual({ id: "pool-1", data: {}, address_type: "IpamIPAddress" });
  });

  it("omits the kind field when no kind was chosen", () => {
    const input = buildAllocateResourceInput({
      poolId: "pool-1",
      poolKind: IP_ADDRESS_POOL,
      poolFieldValue: { from_pool: { id: "pool-1" } },
      nodeData: {},
    });

    expect(input).toEqual({ id: "pool-1", data: {} });
  });
});
