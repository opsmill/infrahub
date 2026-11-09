import { describe, expect, it } from "vitest";

import { buildAllocateResourceInput } from "@/entities/resource-manager/domain/build-allocate-resource-input";

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
});
