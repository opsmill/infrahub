import { describe, expect, it } from "vitest";

import { getJsonPreview } from "./json-preview";

describe("getJsonPreview", () => {
  it("should put a nested value on one line", () => {
    // WHEN
    const result = getJsonPreview({ bgp: { asn: 65_101 }, vlans: [10, 20] });

    // THEN
    expect(result).toBe('{ "bgp": { "asn": 65101 }, "vlans": [ 10, 20 ] }');
  });

  it("should cut a long value to 200 characters", () => {
    // GIVEN
    const value = { description: "x".repeat(500) };

    // WHEN
    const result = getJsonPreview(value);

    // THEN
    expect(result).toHaveLength(200);
  });

  it("should render a scalar as JSON", () => {
    // WHEN
    const result = getJsonPreview("auto");

    // THEN
    expect(result).toBe('"auto"');
  });
});
