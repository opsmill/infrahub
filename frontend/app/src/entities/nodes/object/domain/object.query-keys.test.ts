import { describe, expect, it } from "vitest";

import type { Filter } from "@/shared/hooks/useFilters";

import { objectQueryKeys } from "./object.query-keys";

describe("objectQueryKeys", () => {
  it("returns base query key for all", () => {
    // WHEN
    const result = objectQueryKeys.all;

    // THEN
    expect(result).toEqual(["objects"]);
  });

  it("returns query key for allWithContext", () => {
    // GIVEN
    const contextParams = {
      branchName: "branchName",
      atDate: new Date("2024-01-01"),
    };

    // WHEN
    const result = objectQueryKeys.allWithContext(contextParams);

    // THEN
    expect(result).toEqual(["objects", "branchName", contextParams.atDate]);
  });

  it("returns query key for lists", () => {
    // GIVEN
    const params = {
      branchName: "branchName",
      atDate: new Date("2024-01-01"),
      objectKind: "RandomKind",
    };

    // WHEN
    const result = objectQueryKeys.lists(params);

    // THEN
    expect(result).toEqual(["objects", "branchName", params.atDate, "RandomKind"]);
  });

  it("returns query key for list", () => {
    // GIVEN
    const filters: Filter[] = [{ name: "include_available", value: "true" }];
    const params = {
      branchName: "branchName",
      atDate: new Date("2024-01-01"),
      objectKind: "RandomKind",
      filters,
    };

    // WHEN
    const result = objectQueryKeys.list(params);

    // THEN
    expect(result).toEqual(["objects", "branchName", params.atDate, "RandomKind", filters]);
  });

  it("returns query key for count", () => {
    // GIVEN
    const filters: Filter[] = [{ name: "include_available", value: "true" }];
    const params = {
      branchName: "branchName",
      atDate: new Date("2024-01-01"),
      objectKind: "RandomKind",
      filters,
    };

    // WHEN
    const result = objectQueryKeys.count(params);

    // THEN
    expect(result).toEqual([
      "objects",
      "branchName",
      params.atDate,
      "RandomKind",
      "count",
      filters,
    ]);
  });

  it("returns query key for detail", () => {
    // GIVEN
    const params = {
      branchName: "branchName",
      atDate: new Date("2024-01-01"),
      objectKind: "RandomKind",
      objectId: "123",
    };

    // WHEN
    const result = objectQueryKeys.detail(params);

    // THEN
    expect(result).toEqual(["objects", "branchName", params.atDate, "RandomKind", "123"]);
  });

  it("returns query key for ancestors", () => {
    // GIVEN
    const params = {
      branchName: "branchName",
      atDate: new Date("2024-01-01"),
      objectKind: "RandomKind",
      objectId: "123",
    };

    // WHEN
    const result = objectQueryKeys.ancestors(params);

    // THEN
    expect(result).toEqual([
      "objects",
      "branchName",
      params.atDate,
      "RandomKind",
      "123",
      "ancestors",
    ]);
  });
});
