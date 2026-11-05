import { describe, expect, it } from "vitest";

import { generateNodeSchema } from "../../../../../tests/fake/schema";
import { getWeightedPrefixKinds } from "./get-weighted-prefix-kinds";

describe("getWeightedPrefixKinds", () => {
  it("keeps the prefix kinds that inherit the weighted pool resource generic", () => {
    // GIVEN
    const schemas = [
      generateNodeSchema({
        kind: "InfraWeightedPrefix",
        inherit_from: ["BuiltinIPPrefix", "CoreWeightedPoolResource"],
      }),
      generateNodeSchema({ kind: "IpamIPPrefix", inherit_from: ["BuiltinIPPrefix"] }),
      generateNodeSchema({
        kind: "CoreNumberPoolRange",
        inherit_from: ["CoreWeightedPoolResource"],
      }),
    ];

    // WHEN
    const kinds = getWeightedPrefixKinds(schemas);

    // THEN
    expect(kinds).toEqual(["InfraWeightedPrefix"]);
  });

  it("returns nothing when no prefix kind has a weight", () => {
    // GIVEN
    const schemas = [
      generateNodeSchema({ kind: "IpamIPPrefix", inherit_from: ["BuiltinIPPrefix"] }),
    ];

    // WHEN
    const kinds = getWeightedPrefixKinds(schemas);

    // THEN
    expect(kinds).toEqual([]);
  });
});
