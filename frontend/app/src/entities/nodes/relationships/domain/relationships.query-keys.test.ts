import { describe, expect, it } from "vitest";

import type { Filter } from "@/shared/hooks/useFilters";

import { relationshipsQueryKeys } from "./relationships.query-keys";

describe("relationshipsQueryKeys", () => {
  it("returns query key for lists", () => {
    // GIVEN
    const params = {
      branchName: "branchName",
      atDate: new Date("2024-01-01"),
      objectKind: "RandomKind",
      objectId: "123",
      relationshipName: "relName",
    };

    // WHEN
    const result = relationshipsQueryKeys.lists(params);

    // THEN
    expect(result).toEqual([
      "objects",
      "branchName",
      params.atDate,
      "RandomKind",
      "123",
      "relName",
    ]);
  });

  it("returns query key for list", () => {
    // GIVEN
    const filters: Filter[] = [{ name: "include_available", value: "true" }];
    const params = {
      branchName: "branchName",
      atDate: new Date("2024-01-01"),
      objectKind: "RandomKind",
      objectId: "123",
      relationshipName: "relName",
      filters,
    };

    // WHEN
    const result = relationshipsQueryKeys.list(params);

    // THEN
    expect(result).toEqual([
      "objects",
      "branchName",
      params.atDate,
      "RandomKind",
      "123",
      "relName",
      filters,
    ]);
  });

  it("returns query key for count", () => {
    // GIVEN
    const params = {
      branchName: "branchName",
      atDate: new Date("2024-01-01"),
      objectKind: "RandomKind",
      objectId: "123",
      relationshipName: "relName",
    };

    // WHEN
    const result = relationshipsQueryKeys.count(params);

    // THEN
    expect(result).toEqual([
      "objects",
      "branchName",
      params.atDate,
      "RandomKind",
      "123",
      "relName",
      "count",
    ]);
  });

  it("returns query key for properties", () => {
    // GIVEN
    const params = {
      branchName: "branchName",
      atDate: new Date("2024-01-01"),
      objectKind: "RandomKind",
      objectId: "123",
      relationshipName: "relName",
      relationshipId: "456",
    };

    // WHEN
    const result = relationshipsQueryKeys.properties(params);

    // THEN
    expect(result).toEqual([
      "objects",
      "branchName",
      params.atDate,
      "RandomKind",
      "123",
      "relName",
      "456",
      "properties",
    ]);
  });
});
