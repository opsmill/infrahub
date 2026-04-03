import { describe, expect, it } from "vitest";

import { resolveGlobalPermissionFilters } from "./global-permissions-table";

describe("resolveGlobalPermissionFilters", () => {
  it("maps Allow label to numeric value 6", () => {
    // GIVEN
    const filters = [{ name: "decision__value", value: "Allow" }];

    // WHEN
    const result = resolveGlobalPermissionFilters(filters);

    // THEN
    expect(result).toEqual([{ name: "decision__value", value: 6 }]);
  });

  it("maps Deny label to numeric value 1", () => {
    // GIVEN
    const filters = [{ name: "decision__value", value: "Deny" }];

    // WHEN
    const result = resolveGlobalPermissionFilters(filters);

    // THEN
    expect(result).toEqual([{ name: "decision__value", value: 1 }]);
  });

  it("passes through non-decision filters unchanged", () => {
    // GIVEN
    const filters = [
      { name: "action__value", value: "create" },
      { name: "roles__ids", value: ["id1"] },
    ];

    // WHEN
    const result = resolveGlobalPermissionFilters(filters);

    // THEN
    expect(result).toEqual(filters);
  });

  it("handles mixed filters with decision and non-decision", () => {
    // GIVEN
    const filters = [
      { name: "action__value", value: "create" },
      { name: "decision__value", value: "Allow" },
    ];

    // WHEN
    const result = resolveGlobalPermissionFilters(filters);

    // THEN
    expect(result).toEqual([
      { name: "action__value", value: "create" },
      { name: "decision__value", value: 6 },
    ]);
  });

  it("returns empty array for empty input", () => {
    // GIVEN
    const filters: { name: string; value: unknown }[] = [];

    // WHEN
    const result = resolveGlobalPermissionFilters(filters);

    // THEN
    expect(result).toEqual([]);
  });
});
