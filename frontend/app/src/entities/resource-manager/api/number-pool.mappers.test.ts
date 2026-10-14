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
    ranges: { edges: [] },
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
      ranges: [],
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

  it("reads the field names from the stored scope entries", () => {
    // WHEN
    const pool = mapToNumberPoolData(
      buildNode({
        allocation_scope: {
          value: [
            { id: "field-1", name: "device" },
            { id: "field-2", name: "vrf" },
          ],
        },
      })
    );

    // THEN
    expect(pool.allocation_scope.value).toEqual(["device", "vrf"]);
  });

  it("treats an empty description as missing", () => {
    // WHEN
    const pools = ["", null].map((value) =>
      mapToNumberPoolData(buildNode({ description: { value } }))
    );

    // THEN
    expect(pools.map((pool) => pool.description.value)).toEqual([null, null]);
  });

  it("maps the stored ranges, keeping a range without a weight apart from weight 0", () => {
    // GIVEN
    const node = buildNode({
      ranges: {
        edges: [
          {
            node: {
              start: { value: 100 },
              end: { value: 199 },
              allocation_weight: { value: 10 },
            },
          },
          {
            node: {
              start: { value: 300 },
              end: { value: 399 },
              allocation_weight: { value: null },
            },
          },
          { node: { start: { value: 500 }, end: { value: 599 }, allocation_weight: { value: 0 } } },
        ],
      },
    });

    // WHEN
    const pool = mapToNumberPoolData(node);

    // THEN
    expect(pool.ranges).toEqual([
      { start: 100, end: 199, allocation_weight: 10 },
      { start: 300, end: 399, allocation_weight: null },
      { start: 500, end: 599, allocation_weight: 0 },
    ]);
  });
});
