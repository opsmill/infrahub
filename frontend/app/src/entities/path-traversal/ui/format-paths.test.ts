import { describe, expect, test } from "vitest";

import type {
  PathHop,
  PathNode,
  PathResult,
  PathTraversalResponse,
} from "../domain/path-traversal.types";
import { copyAllPathsAsText, formatPathAsText, getKindCounts, pathPreview } from "./format-paths";

const node = (id: string, kind: string, label: string): PathNode => ({
  id,
  kind,
  label: kind,
  display_label: label,
  hfid: [label],
});

const a = node("a", "InfraDevice", "router-1");
const b = node("b", "InfraInterface", "Ethernet1");
const c = node("c", "InfraDevice", "router-2");

const rel = (from: string, to: string) => ({
  from_rel: from,
  from_label: from,
  to_rel: to,
  to_label: to,
  kind: "Generic",
});

const hop = (n: PathNode, relationship: PathHop["relationship"] = null): PathHop => ({
  node: n,
  relationship,
});

const path: PathResult = {
  hops: [hop(a), hop(b, rel("interfaces", "device")), hop(c, rel("device", "interfaces"))],
  depth: 2,
};

const response: PathTraversalResponse = {
  paths: [path],
  source: a,
  destination: c,
  count: 1,
};

describe("formatPathAsText", () => {
  test("renders nodes joined by relationship labels", () => {
    expect(formatPathAsText(response, 0)).toBe(
      "router-1 -[interfaces]-> Ethernet1 -[device]-> router-2"
    );
  });

  test("falls back to a plain arrow when a relationship is missing", () => {
    const broken: PathTraversalResponse = {
      ...response,
      paths: [{ ...path, hops: [hop(a), hop(b, rel("interfaces", "device")), hop(c)] }],
    };
    expect(formatPathAsText(broken, 0)).toBe("router-1 -[interfaces]-> Ethernet1 -> router-2");
  });

  test("returns empty string for an out-of-range path index", () => {
    expect(formatPathAsText(response, 5)).toBe("");
  });
});

describe("copyAllPathsAsText", () => {
  test("renders one numbered line per path", () => {
    const shortPath: PathResult = {
      hops: [hop(a), hop(c, rel("device", "interfaces"))],
      depth: 1,
    };
    const data: PathTraversalResponse = {
      ...response,
      paths: [path, shortPath],
      count: 2,
    };
    expect(copyAllPathsAsText(data)).toBe(
      "Path 1: router-1 → Ethernet1 → router-2\nPath 2: router-1 → router-2"
    );
  });

  test("returns empty string for zero paths", () => {
    expect(copyAllPathsAsText({ ...response, paths: [], count: 0 })).toBe("");
  });
});

describe("pathPreview", () => {
  test("returns the full chain when nodes fit under the limit", () => {
    expect(pathPreview(path, 5)).toBe("router-1 -> Ethernet1 -> router-2");
  });

  test("returns first -> ... -> last when nodes exceed the limit", () => {
    const longPath: PathResult = {
      ...path,
      hops: [
        hop(a),
        hop(b, rel("interfaces", "device")),
        hop(c, rel("device", "interfaces")),
        hop(node("d", "InfraDevice", "router-3"), rel("link", "link")),
      ],
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

  test("returns an empty string for a path with no hops", () => {
    expect(getKindCounts({ ...path, hops: [] })).toBe("");
  });
});
