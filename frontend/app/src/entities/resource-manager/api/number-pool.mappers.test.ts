import { describe, expect, it } from "vitest";

import type { NumberPoolNode } from "./get-number-pool-from-api";
import { mapToNumberPoolData } from "./number-pool.mappers";

const buildNode = (overrides: Partial<Record<keyof NumberPoolNode, unknown>> = {}) =>
  ({
    id: "pool-id",
    hfid: ["Interface speeds"],
    display_label: "Interface speeds",
    __typename: "CoreNumberPool",
    name: { value: "Interface speeds" },
    description: { value: "Speeds for new interfaces" },
    pool_type: { value: "User" },
    node: { value: "InfraInterface" },
    node_attribute: { value: "speed" },
    allocation_scope: { value: null },
    ...overrides,
  }) as NumberPoolNode;

describe("mapToNumberPoolData", () => {
  it("maps the stored fields", () => {
    // WHEN
    const pool = mapToNumberPoolData(buildNode());

    // THEN
    expect(pool).toEqual({
      id: "pool-id",
      hfid: ["Interface speeds"],
      display_label: "Interface speeds",
      __typename: "CoreNumberPool",
      name: { value: "Interface speeds" },
      description: { value: "Speeds for new interfaces" },
      pool_type: { value: "User" },
      node: { value: "InfraInterface" },
      node_attribute: { value: "speed" },
      allocation_scope: { value: [] },
    });
  });

  it("keeps the schema pool type", () => {
    // WHEN
    const pool = mapToNumberPoolData(buildNode({ pool_type: { value: "Schema" } }));

    // THEN
    expect(pool.pool_type.value).toBe("Schema");
  });

  it("treats a missing or unknown pool type as created by a user", () => {
    // WHEN
    const pools = [null, "Other"].map((value) =>
      mapToNumberPoolData(buildNode({ pool_type: { value } }))
    );

    // THEN
    expect(pools.map((pool) => pool.pool_type.value)).toEqual(["User", "User"]);
  });

  it("keeps the allocation scope field names", () => {
    // WHEN
    const pool = mapToNumberPoolData(buildNode({ allocation_scope: { value: ["site", "role"] } }));

    // THEN
    expect(pool.allocation_scope.value).toEqual(["site", "role"]);
  });

  it("drops an allocation scope that is not a list of field names", () => {
    // WHEN
    const pools = [[1], "site", {}].map((value) =>
      mapToNumberPoolData(buildNode({ allocation_scope: { value } }))
    );

    // THEN
    expect(pools.map((pool) => pool.allocation_scope.value)).toEqual([[], [], []]);
  });

  it("treats an empty description as missing", () => {
    // WHEN
    const pools = ["", null].map((value) =>
      mapToNumberPoolData(buildNode({ description: { value } }))
    );

    // THEN
    expect(pools.map((pool) => pool.description.value)).toEqual([null, null]);
  });
});
