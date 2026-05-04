import { describe, expect, test } from "vitest";

import type { PathResult, PathTraversalResponse } from "../domain/get-path-traversal";
import { copyAllPathsAsText, formatPathAsText, getKindCounts, pathPreview } from "./format-paths";

const a = { id: "a", kind: "InfraDevice", display_label: "router-1" };
const b = { id: "b", kind: "InfraInterface", display_label: "Ethernet1" };
const c = { id: "c", kind: "InfraDevice", display_label: "router-2" };

const rel = (name: string) => ({ id: `r-${name}`, name, direction: "OUTBOUND" as const });

const path: PathResult = {
  objects: [a, b, c],
  relationships: [rel("device__interfaces"), rel("interface__device")],
  depth: 2,
};

const response: PathTraversalResponse = {
  paths: [path],
  source: a,
  destination: c,
  total_paths_found: 1,
};

describe("formatPathAsText", () => {
  test("renders objects joined by relationship names", () => {
    expect(formatPathAsText(response, 0)).toBe(
      "router-1 -[device / interfaces]-> Ethernet1 -[interface / device]-> router-2"
    );
  });

  test("falls back to a plain arrow when a relationship is missing", () => {
    const broken: PathTraversalResponse = {
      ...response,
      paths: [{ ...path, relationships: [rel("device__interfaces")] }],
    };
    expect(formatPathAsText(broken, 0)).toBe(
      "router-1 -[device / interfaces]-> Ethernet1  ->  router-2"
    );
  });

  test("returns empty string for an out-of-range path index", () => {
    expect(formatPathAsText(response, 5)).toBe("");
  });
});

describe("copyAllPathsAsText", () => {
  test("renders one numbered line per path", () => {
    const data: PathTraversalResponse = {
      ...response,
      paths: [path, { ...path, objects: [a, c], relationships: [rel("foo")], depth: 1 }],
      total_paths_found: 2,
    };
    expect(copyAllPathsAsText(data)).toBe(
      "Path 1: router-1 → Ethernet1 → router-2\nPath 2: router-1 → router-2"
    );
  });

  test("returns empty string for zero paths", () => {
    expect(copyAllPathsAsText({ ...response, paths: [], total_paths_found: 0 })).toBe("");
  });
});

describe("pathPreview", () => {
  test("returns the full chain when objects fit under the limit", () => {
    expect(pathPreview(path, 5)).toBe("router-1 -> Ethernet1 -> router-2");
  });

  test("returns first -> ... -> last when objects exceed the limit", () => {
    const longPath: PathResult = {
      ...path,
      objects: [a, b, c, { ...a, id: "d", display_label: "router-3" }],
    };
    expect(pathPreview(longPath, 3)).toBe("router-1 -> ... -> router-3");
  });

  test("uses default limit of 3", () => {
    expect(pathPreview(path)).toBe("router-1 -> Ethernet1 -> router-2");
  });
});

describe("getKindCounts", () => {
  test("counts and labels each kind on the path", () => {
    expect(getKindCounts(path)).toBe("2x InfraDevice, 1x InfraInterface");
  });

  test("returns an empty string for a path with no objects", () => {
    expect(getKindCounts({ ...path, objects: [] })).toBe("");
  });
});
