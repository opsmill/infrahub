import { describe, expect, it } from "vitest";

import { buildFromPoolPayload } from "@/shared/components/form/utils/mutations/buildFromPoolMutationValue";

import { IP_ADDRESS_POOL, IP_PREFIX_POOL } from "@/entities/resource-manager/domain/model/pool";

describe("buildFromPoolPayload", () => {
  it("omits the prefix length when none was entered", () => {
    expect(buildFromPoolPayload({ id: "pool1" }, IP_ADDRESS_POOL)).toEqual({ id: "pool1" });
    expect(buildFromPoolPayload({ id: "pool1", prefixLength: null }, IP_PREFIX_POOL)).toEqual({
      id: "pool1",
    });
  });

  it("sends the prefix length as `prefixlen` for an IP address pool", () => {
    expect(buildFromPoolPayload({ id: "pool1", prefixLength: 24 }, IP_ADDRESS_POOL)).toEqual({
      id: "pool1",
      prefixlen: 24,
    });
  });

  it("sends the prefix length as `size` for an IP prefix pool", () => {
    expect(buildFromPoolPayload({ id: "pool1", prefixLength: 30 }, IP_PREFIX_POOL)).toEqual({
      id: "pool1",
      size: 30,
    });
  });

  it("defaults to `prefixlen` when the pool kind is unknown", () => {
    expect(buildFromPoolPayload({ id: "pool1", prefixLength: 24 })).toEqual({
      id: "pool1",
      prefixlen: 24,
    });
  });
});
