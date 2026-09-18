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

  it("restores the existing allocation when the original pool is re-selected, ignoring a new prefixLength", () => {
    // Allocation is idempotent: re-selecting the field's original pool cannot change
    // its mask, so the resolved value is restored rather than a pending allocation.
    const result = updateRelationshipFieldValue(
      {
        from_pool: {
          id: "loopbacks",
          name: "Loopbacks pool",
          kind: "CoreIPAddressPool",
          prefixLength: 28,
        },
      },
      original
    );

    expect(result).toBe(original);
  });

  it("creates a pending allocation when a different pool is selected, carrying its prefixLength", () => {
    const result = updateRelationshipFieldValue(
      {
        from_pool: {
          id: "management",
          name: "Management addresses pool",
          kind: "CoreIPAddressPool",
          prefixLength: 16,
          defaultPrefixLength: 8,
        },
      },
      original
    );

    // The pool default is kept on the source (for the placeholder) but never in the
    // value, which carries only what the mutation sends (id + the typed prefixLength).
    expect(result).toEqual({
      source: {
        type: "pool",
        id: "management",
        kind: "CoreIPAddressPool",
        label: "Management addresses pool",
        defaultPrefixLength: 8,
        defaultAllocatedKind: null,
      },
      value: { from_pool: { id: "management", prefixLength: 16 } },
    });
  });

  it("restores the existing allocation when the original pool is re-selected with the kind it already holds", () => {
    const result = updateRelationshipFieldValue(
      {
        from_pool: {
          id: "loopbacks",
          name: "Loopbacks pool",
          kind: "CoreIPAddressPool",
          allocatedKind: "IpamIPAddress",
        },
      },
      original
    );

    expect(result).toBe(original);
  });

  it("creates a pending allocation when the original pool is re-selected with a different kind", () => {
    // No reservation identifier is sent for the kind, so a different kind is a fresh allocation, not a no-op.
    const result = updateRelationshipFieldValue(
      {
        from_pool: {
          id: "loopbacks",
          name: "Loopbacks pool",
          kind: "CoreIPAddressPool",
          allocatedKind: "InfraIPAddress",
        },
      },
      original
    );

    expect(result).toEqual({
      source: {
        type: "pool",
        id: "loopbacks",
        kind: "CoreIPAddressPool",
        label: "Loopbacks pool",
        defaultPrefixLength: null,
        defaultAllocatedKind: null,
      },
      value: { from_pool: { id: "loopbacks", allocatedKind: "InfraIPAddress" } },
    });
  });

  it("creates a pending allocation carrying the chosen allocatedKind, distinct from the pool's own kind", () => {
    const result = updateRelationshipFieldValue(
      {
        from_pool: {
          id: "management",
          name: "Management addresses pool",
          kind: "CoreIPAddressPool",
          allocatedKind: "IpamIPAddress",
        },
      },
      original
    );

    // `kind` is the pool's own __typename; `allocatedKind` is what the mutation sends.
    expect(result).toEqual({
      source: {
        type: "pool",
        id: "management",
        kind: "CoreIPAddressPool",
        label: "Management addresses pool",
        defaultPrefixLength: null,
        defaultAllocatedKind: null,
      },
      value: { from_pool: { id: "management", allocatedKind: "IpamIPAddress" } },
    });
  });

  it("omits allocatedKind from the value when no kind was chosen", () => {
    const result = updateRelationshipFieldValue(
      {
        from_pool: {
          id: "management",
          name: "Management addresses pool",
          kind: "CoreIPAddressPool",
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
        defaultPrefixLength: null,
        defaultAllocatedKind: null,
      },
      value: { from_pool: { id: "management" } },
    });
  });

  it("carries the pool's own default kind onto the source, for the override placeholder", () => {
    const result = updateRelationshipFieldValue(
      {
        from_pool: {
          id: "management",
          name: "Management addresses pool",
          kind: "CoreIPAddressPool",
          defaultAllocatedKind: "IpamIPAddress",
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
        defaultPrefixLength: null,
        defaultAllocatedKind: "IpamIPAddress",
      },
      value: { from_pool: { id: "management" } },
    });
  });

  it("drops both IP-only pool defaults for a number pool", () => {
    const result = updateRelationshipFieldValue(
      {
        from_pool: {
          id: "numbers",
          name: "Numbers pool",
          kind: "CoreNumberPool",
          defaultPrefixLength: 24,
          defaultAllocatedKind: "IpamIPAddress",
        },
      },
      original
    );

    expect(result).toEqual({
      source: { type: "pool", id: "numbers", kind: "CoreNumberPool", label: "Numbers pool" },
      value: { from_pool: { id: "numbers" } },
    });
  });
});

describe("updateAttributeFieldValue - from-pool", () => {
  const original: FormAttributeValue = {
    source: { type: "pool", id: "loopbacks", kind: "CoreIPAddressPool", label: "Loopbacks pool" },
    value: { from_pool: { id: "loopbacks", prefixLength: 24, allocatedKind: "IpamIPAddress" } },
  };

  it("restores the existing allocation when the original pool is re-selected, ignoring a new prefixLength", () => {
    const result = updateAttributeFieldValue(
      {
        from_pool: {
          id: "loopbacks",
          name: "Loopbacks pool",
          kind: "CoreIPAddressPool",
          prefixLength: 28,
        },
      },
      original
    );

    expect(result).toBe(original);
  });

  it("creates a pending allocation when a different pool is selected, carrying its prefixLength", () => {
    const result = updateAttributeFieldValue(
      {
        from_pool: {
          id: "management",
          name: "Management addresses pool",
          kind: "CoreIPAddressPool",
          prefixLength: 16,
          defaultPrefixLength: 8,
        },
      },
      original
    );

    // The pool default is kept on the source (for the placeholder) but never in the
    // value, which carries only what the mutation sends (id + the typed prefixLength).
    expect(result).toEqual({
      source: {
        type: "pool",
        id: "management",
        kind: "CoreIPAddressPool",
        label: "Management addresses pool",
        defaultPrefixLength: 8,
        defaultAllocatedKind: null,
      },
      value: { from_pool: { id: "management", prefixLength: 16 } },
    });
  });

  it("restores the existing allocation when the original pool is re-selected with the kind it already holds", () => {
    const result = updateAttributeFieldValue(
      {
        from_pool: {
          id: "loopbacks",
          name: "Loopbacks pool",
          kind: "CoreIPAddressPool",
          allocatedKind: "IpamIPAddress",
        },
      },
      original
    );

    expect(result).toBe(original);
  });

  it("creates a pending allocation when the original pool is re-selected with a different kind", () => {
    // A different kind is a real request, not a no-op, so it must not collapse back.
    const result = updateAttributeFieldValue(
      {
        from_pool: {
          id: "loopbacks",
          name: "Loopbacks pool",
          kind: "CoreIPAddressPool",
          allocatedKind: "InfraIPAddress",
        },
      },
      original
    );

    expect(result).toEqual({
      source: {
        type: "pool",
        id: "loopbacks",
        kind: "CoreIPAddressPool",
        label: "Loopbacks pool",
        defaultPrefixLength: null,
        defaultAllocatedKind: null,
      },
      value: { from_pool: { id: "loopbacks", allocatedKind: "InfraIPAddress" } },
    });
  });

  it("creates a pending allocation carrying the chosen allocatedKind, distinct from the pool's own kind", () => {
    const result = updateAttributeFieldValue(
      {
        from_pool: {
          id: "management",
          name: "Management addresses pool",
          kind: "CoreIPAddressPool",
          allocatedKind: "IpamIPAddress",
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
        defaultPrefixLength: null,
        defaultAllocatedKind: null,
      },
      value: { from_pool: { id: "management", allocatedKind: "IpamIPAddress" } },
    });
  });

  it("omits allocatedKind from the value when no kind was chosen", () => {
    const result = updateAttributeFieldValue(
      {
        from_pool: {
          id: "management",
          name: "Management addresses pool",
          kind: "CoreIPAddressPool",
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
        defaultPrefixLength: null,
        defaultAllocatedKind: null,
      },
      value: { from_pool: { id: "management" } },
    });
  });

  it("carries the pool's own default kind onto the source, for the override placeholder", () => {
    const result = updateAttributeFieldValue(
      {
        from_pool: {
          id: "management",
          name: "Management addresses pool",
          kind: "CoreIPAddressPool",
          defaultAllocatedKind: "IpamIPAddress",
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
        defaultPrefixLength: null,
        defaultAllocatedKind: "IpamIPAddress",
      },
      value: { from_pool: { id: "management" } },
    });
  });

  it("drops both IP-only pool defaults for a number pool", () => {
    const result = updateAttributeFieldValue(
      {
        from_pool: {
          id: "numbers",
          name: "Numbers pool",
          kind: "CoreNumberPool",
          defaultPrefixLength: 24,
          defaultAllocatedKind: "IpamIPAddress",
        },
      },
      original
    );

    expect(result).toEqual({
      source: { type: "pool", id: "numbers", kind: "CoreNumberPool", label: "Numbers pool" },
      value: { from_pool: { id: "numbers" } },
    });
  });
});
