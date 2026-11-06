import { describe, expect, it } from "vitest";

import { buildIpPoolResourceWeightsQuery } from "./get-ip-pool-resource-weights-from-api";

describe("buildIpPoolResourceWeightsQuery", () => {
  it("reads the weight of the given resource prefixes on each weighted prefix kind", () => {
    // GIVEN
    const params = { resourceIds: ["r1"], weightedKinds: ["IpamIPPrefix"] };

    // WHEN
    const query = buildIpPoolResourceWeightsQuery(params).replace(/\s+/g, " ").replace(/ \(/g, "(");

    // THEN
    expect(query).toContain('BuiltinIPPrefix(ids: ["r1"])');
    expect(query).toContain("... on IpamIPPrefix");
    expect(query).toContain("allocation_weight");
  });
});
