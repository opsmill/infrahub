import { describe, expect, it } from "vitest";

import type { NumberPoolForEditingNode } from "@/entities/resource-manager/api/get-number-pool-for-editing-from-api";

import { toNumberPoolForEditing } from "./number-pool.mappers";

const rangeNode = (id: string, start: unknown, end: unknown, weight: unknown) => ({
  node: {
    id,
    start: { value: start },
    end: { value: end },
    allocation_weight: { value: weight },
  },
});

const poolNode = (overrides: Partial<NumberPoolForEditingNode> = {}): NumberPoolForEditingNode => ({
  id: "pool-1",
  name: { value: "VLAN pool" },
  description: { value: "Campus VLANs" },
  node: { value: "InfraVLAN" },
  node_attribute: { value: "vlan_id" },
  allocation_scope: { value: ["site"] },
  pool_type: { value: "User" },
  ranges: { edges: [rangeNode("r-1", 100, 199, 10), rangeNode("r-2", -5, 5, null)] },
  ...overrides,
});

describe("toNumberPoolForEditing", () => {
  it("maps the pool fields and its ranges", () => {
    // GIVEN a user pool with two ranges, one without weight
    const node = poolNode();

    // WHEN mapped
    const pool = toNumberPoolForEditing(node);

    // THEN every field is read from its attribute value
    expect(pool).toEqual({
      id: "pool-1",
      name: "VLAN pool",
      description: "Campus VLANs",
      node: "InfraVLAN",
      nodeAttribute: "vlan_id",
      allocationScope: ["site"],
      poolType: "User",
      ranges: [
        { id: "r-1", start: 100n, end: 199n, weight: 10 },
        { id: "r-2", start: -5n, end: 5n, weight: null },
      ],
    });
  });

  it("converts bounds and weight sent as strings", () => {
    // GIVEN a range whose BigInt values arrive as strings
    const node = poolNode({ ranges: { edges: [rangeNode("r-1", "1", "4094", "0")] } });

    // WHEN mapped
    const pool = toNumberPoolForEditing(node);

    // THEN the bounds are whole numbers, and a zero weight stays zero
    expect(pool.ranges).toEqual([{ id: "r-1", start: 1n, end: 4094n, weight: 0 }]);
  });

  it("keeps a bound above 2^53 exact", () => {
    // GIVEN a range ending at the largest 64-bit integer, which the API returns as a string
    const node = poolNode({
      ranges: { edges: [rangeNode("r-1", 1, "9223372036854775807", null)] },
    });

    // WHEN mapped
    const pool = toNumberPoolForEditing(node);

    // THEN the end is the exact value
    expect(pool.ranges[0]?.end).toBe(9223372036854775807n);
  });

  it("reads a scope stored as id and name objects by its names", () => {
    // GIVEN a scope returned as schema element ids with their names
    const node = poolNode({
      allocation_scope: {
        value: [
          { id: "17d0a4c2", name: "site" },
          { id: "3b1f90ee", name: "role" },
        ],
      },
    });

    // WHEN mapped
    const pool = toNumberPoolForEditing(node);

    // THEN the scope holds the names, in order
    expect(pool.allocationScope).toEqual(["site", "role"]);
  });

  it("reads a scope element given as an object with a name only", () => {
    // GIVEN a scope mixing a name and an object without id
    const node = poolNode({ allocation_scope: { value: ["site", { name: "role" }] } });

    // WHEN mapped
    const pool = toNumberPoolForEditing(node);

    // THEN both elements are read by their names
    expect(pool.allocationScope).toEqual(["site", "role"]);
  });

  it("maps a schema-defined pool", () => {
    // GIVEN a pool created by the schema
    const node = poolNode({ pool_type: { value: "Schema" } });

    // WHEN mapped
    const pool = toNumberPoolForEditing(node);

    // THEN the pool type is Schema
    expect(pool.poolType).toBe("Schema");
  });

  it("uses empty values when optional attributes are missing", () => {
    // GIVEN a pool without description and without allocation scope
    const node = poolNode({
      description: { value: null },
      allocation_scope: null,
      ranges: { edges: [] },
    });

    // WHEN mapped
    const pool = toNumberPoolForEditing(node);

    // THEN description is empty, scope is an empty list and there are no ranges
    expect(pool.description).toBe("");
    expect(pool.allocationScope).toEqual([]);
    expect(pool.ranges).toEqual([]);
  });
});
