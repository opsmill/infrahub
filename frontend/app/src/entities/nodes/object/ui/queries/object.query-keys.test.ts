import { describe, expect, it } from "vitest";

import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { Sort } from "@/entities/nodes/sort/domain/model/sort";

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

  it("returns query key for list including filters and sort", () => {
    // GIVEN
    const filters: Filter[] = [{ name: "include_available", value: "true" }];
    const sort: Sort[] = [{ field: "name__value", direction: "ASC" }];
    const params = {
      branchName: "branchName",
      atDate: new Date("2024-01-01"),
      objectKind: "RandomKind",
      filters,
      sort,
    };

    // WHEN
    const result = objectQueryKeys.list(params);

    // THEN
    expect(result).toEqual(["objects", "branchName", params.atDate, "RandomKind", filters, sort]);
  });

  it("returns query key for list unchanged when revealedFields is absent or empty, so existing caches stay valid", () => {
    // GIVEN
    const filters: Filter[] = [{ name: "include_available", value: "true" }];
    const sort: Sort[] = [{ field: "name__value", direction: "ASC" }];
    const params = {
      branchName: "branchName",
      atDate: new Date("2024-01-01"),
      objectKind: "RandomKind",
      filters,
      sort,
    };

    // WHEN
    const withoutRevealedFields = objectQueryKeys.list(params);
    const withEmptyRevealedFields = objectQueryKeys.list({ ...params, revealedFields: [] });

    // THEN
    expect(withoutRevealedFields).toEqual([
      "objects",
      "branchName",
      params.atDate,
      "RandomKind",
      filters,
      sort,
    ]);
    expect(withEmptyRevealedFields).toEqual(withoutRevealedFields);
  });

  it("returns query key for list including revealedFields, so a revealed column never reads a page fetched without it", () => {
    // GIVEN
    const filters: Filter[] = [{ name: "include_available", value: "true" }];
    const sort: Sort[] = [{ field: "name__value", direction: "ASC" }];
    const params = {
      branchName: "branchName",
      atDate: new Date("2024-01-01"),
      objectKind: "RandomKind",
      filters,
      sort,
      revealedFields: ["internal_note"],
    };

    // WHEN
    const result = objectQueryKeys.list(params);

    // THEN
    expect(result).toEqual([
      "objects",
      "branchName",
      params.atDate,
      "RandomKind",
      filters,
      sort,
      ["internal_note"],
    ]);
  });

  it("returns query key for count without sort, since sort never changes the row count", () => {
    // GIVEN
    const filters: Filter[] = [{ name: "include_available", value: "true" }];
    const sort: Sort[] = [{ field: "name__value", direction: "ASC" }];
    const params = {
      branchName: "branchName",
      atDate: new Date("2024-01-01"),
      objectKind: "RandomKind",
      filters,
      sort,
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
