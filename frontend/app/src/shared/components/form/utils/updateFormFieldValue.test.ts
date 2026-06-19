import { describe, expect, it } from "vitest";

import type { FormAttributeValue, FormRelationshipValue } from "@/shared/components/form/type";
import {
  updateAttributeFieldValue,
  updateRelationshipFieldValue,
} from "@/shared/components/form/utils/updateFormFieldValue";

describe("updateRelationshipFieldValue - from-pool", () => {
  const original: FormRelationshipValue = {
    source: { type: "pool", id: "loopbacks", kind: "CoreIPAddressPool", label: "Loopbacks pool" },
    value: { id: "addr-id", display_label: "10.0.0.31/24", __typename: "IpamIPAddress" },
  };

  it("restores the existing allocation when the original pool is re-selected, ignoring a new prefixlen", () => {
    // Allocation is idempotent: re-selecting the field's original pool cannot change
    // its mask, so the resolved value is restored rather than a pending allocation.
    const result = updateRelationshipFieldValue(
      {
        from_pool: {
          id: "loopbacks",
          name: "Loopbacks pool",
          kind: "CoreIPAddressPool",
          prefixlen: 28,
        },
      },
      original
    );

    expect(result).toBe(original);
  });

  it("creates a pending allocation when a different pool is selected, carrying its prefixlen", () => {
    const result = updateRelationshipFieldValue(
      {
        from_pool: {
          id: "management",
          name: "Management addresses pool",
          kind: "CoreIPAddressPool",
          prefixlen: 16,
        },
      },
      original
    );

    expect(result).toEqual({
      source: {
        type: "pool",
        id: "management",
        kind: "CoreIPAddressPool",
        label: "Management addresses pool",
      },
      value: { from_pool: { id: "management", prefixlen: 16 } },
    });
  });
});

describe("updateAttributeFieldValue - from-pool", () => {
  const original: FormAttributeValue = {
    source: { type: "pool", id: "loopbacks", kind: "CoreIPAddressPool", label: "Loopbacks pool" },
    value: { id: "addr-id", display_label: "10.0.0.31/24", __typename: "IpamIPAddress" },
  };

  it("restores the existing allocation when the original pool is re-selected, ignoring a new prefixlen", () => {
    const result = updateAttributeFieldValue(
      {
        from_pool: {
          id: "loopbacks",
          name: "Loopbacks pool",
          kind: "CoreIPAddressPool",
          prefixlen: 28,
        },
      },
      original
    );

    expect(result).toBe(original);
  });

  it("creates a pending allocation when a different pool is selected, carrying its prefixlen", () => {
    const result = updateAttributeFieldValue(
      {
        from_pool: {
          id: "management",
          name: "Management addresses pool",
          kind: "CoreIPAddressPool",
          prefixlen: 16,
        },
      },
      original
    );

    expect(result).toEqual({
      source: {
        type: "pool",
        id: "management",
        kind: "CoreIPAddressPool",
        label: "Management addresses pool",
      },
      value: { from_pool: { id: "management", prefixlen: 16 } },
    });
  });
});
