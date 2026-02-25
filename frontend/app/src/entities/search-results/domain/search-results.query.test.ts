import { describe, expect, it } from "vitest";

import { groupSearchResultsByKind } from "@/entities/search-results/domain/search-results.query";

describe("groupSearchResultsByKind", () => {
  it("groups results by kind and sorts by count descending", () => {
    // GIVEN
    const results = [
      { id: "1", kind: "InfraDevice" },
      { id: "2", kind: "InfraInterface" },
      { id: "3", kind: "InfraDevice" },
      { id: "4", kind: "InfraDevice" },
      { id: "5", kind: "InfraInterface" },
      { id: "6", kind: "LocationSite" },
    ];

    // WHEN
    const groups = groupSearchResultsByKind(results);

    // THEN
    expect(groups).toHaveLength(3);

    const [first, second, third] = groups;
    expect(first!.kind).toBe("InfraDevice");
    expect(first!.count).toBe(3);
    expect(first!.results).toEqual([
      { id: "1", kind: "InfraDevice" },
      { id: "3", kind: "InfraDevice" },
      { id: "4", kind: "InfraDevice" },
    ]);
    expect(second!.kind).toBe("InfraInterface");
    expect(second!.count).toBe(2);
    expect(third!.kind).toBe("LocationSite");
    expect(third!.count).toBe(1);
  });

  it("returns empty array for empty input", () => {
    // GIVEN
    const results: Array<{ id: string; kind: string }> = [];

    // WHEN
    const groups = groupSearchResultsByKind(results);

    // THEN
    expect(groups).toEqual([]);
  });

  it("returns a single group when all results have the same kind", () => {
    // GIVEN
    const results = [
      { id: "1", kind: "InfraDevice" },
      { id: "2", kind: "InfraDevice" },
    ];

    // WHEN
    const groups = groupSearchResultsByKind(results);

    // THEN
    expect(groups).toHaveLength(1);
    expect(groups[0]!.kind).toBe("InfraDevice");
    expect(groups[0]!.label).toBe("InfraDevice");
    expect(groups[0]!.count).toBe(2);
  });

  it("sets label equal to kind for each group", () => {
    // GIVEN
    const results = [{ id: "1", kind: "LocationSite" }];

    // WHEN
    const groups = groupSearchResultsByKind(results);

    // THEN
    expect(groups[0]!.label).toBe("LocationSite");
  });
});
