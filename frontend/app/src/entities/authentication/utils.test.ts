import { describe, expect, it } from "vitest";

import { pathToString, safeInternalPath } from "./utils";

describe("safeInternalPath", () => {
  // The original window.location.origin in vitest's jsdom is `http://localhost:3000`.
  // The helper compares against `window.location.origin`, so the absolute-URL
  // cases below use that origin as the same-origin baseline.

  it("returns null for null / undefined / empty", () => {
    // GIVEN no value
    // THEN nothing to redirect to
    expect(safeInternalPath(null)).toBeNull();
    expect(safeInternalPath(undefined)).toBeNull();
    expect(safeInternalPath("")).toBeNull();
  });

  it("accepts a plain path", () => {
    // GIVEN a path-absolute reference
    // WHEN validated
    // THEN it's parsed into a Partial<Path>
    expect(safeInternalPath("/objects/Device")).toEqual({
      pathname: "/objects/Device",
      search: "",
      hash: "",
    });
  });

  it("preserves search and hash on an internal path", () => {
    // GIVEN a path with query + hash
    // THEN both components survive the round-trip
    expect(safeInternalPath("/foo?bar=1&baz=2#section")).toEqual({
      pathname: "/foo",
      search: "?bar=1&baz=2",
      hash: "#section",
    });
  });

  it("rejects protocol-relative URLs (//evil.com)", () => {
    // GIVEN a protocol-relative reference that browsers resolve cross-origin
    // THEN the open-redirect guard blocks it
    expect(safeInternalPath("//evil.com")).toBeNull();
    expect(safeInternalPath("//evil.com/path")).toBeNull();
  });

  it("rejects schemed URLs (http/https/javascript)", () => {
    // GIVEN an absolute URL with a scheme
    // THEN the leading-slash gate rejects it before URL parsing even runs
    expect(safeInternalPath("https://evil.com/path")).toBeNull();
    expect(safeInternalPath("http://evil.com")).toBeNull();
    expect(safeInternalPath("javascript:alert(1)")).toBeNull();
  });

  it("rejects references that don't start with a single /", () => {
    // GIVEN a relative reference (no leading slash)
    // THEN it's rejected — only path-absolute is allowed
    expect(safeInternalPath("foo")).toBeNull();
    expect(safeInternalPath("./foo")).toBeNull();
    expect(safeInternalPath("../foo")).toBeNull();
  });
});

describe("pathToString", () => {
  it("serialises a full Path object", () => {
    expect(pathToString({ pathname: "/foo", search: "?a=1", hash: "#x" })).toBe("/foo?a=1#x");
  });

  it("defaults missing components", () => {
    expect(pathToString({})).toBe("/");
    expect(pathToString({ pathname: "/foo" })).toBe("/foo");
  });
});
