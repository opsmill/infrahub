import { describe, expect, it } from "vitest";

import { generateAttributeSchema, generateNodeSchema } from "../../../../../tests/fake/schema";
import { getWeightedPrefixKinds } from "./get-weighted-prefix-kinds";

const weight = generateAttributeSchema({ name: "allocation_weight", kind: "Number" });

describe("getWeightedPrefixKinds", () => {
  it("keeps the prefix kinds that carry an allocation weight", () => {
    // GIVEN
    const schemas = [
      generateNodeSchema({
        kind: "IpamIPPrefix",
        inherit_from: ["BuiltinIPPrefix"],
        attributes: [weight],
      }),
      generateNodeSchema({
        kind: "IpamIPPrefixPlain",
        inherit_from: ["BuiltinIPPrefix"],
        attributes: [],
      }),
      generateNodeSchema({
        kind: "CoreNumberPoolRange",
        inherit_from: ["CoreWeightedPoolResource"],
        attributes: [weight],
      }),
    ];

    // WHEN
    const kinds = getWeightedPrefixKinds(schemas);

    // THEN
    expect(kinds).toEqual(["IpamIPPrefix"]);
  });

  it("returns nothing when no prefix kind has a weight", () => {
    // WHEN
    const kinds = getWeightedPrefixKinds([]);

    // THEN
    expect(kinds).toEqual([]);
  });
});
