import { describe, expect, test } from "vitest";

import { mapSubmitErrors } from "./map-submit-errors";

describe("mapSubmitErrors", () => {
  test("maps a message naming a rendered field to that field", () => {
    expect(
      mapSubmitErrors("bandwidth must be at most 1000 at bandwidth", ["name", "bandwidth"])
    ).toEqual({
      fieldErrors: { bandwidth: "bandwidth must be at most 1000 at bandwidth" },
      formError: null,
    });
  });

  test("prefers the key after 'at' over another field mentioned in the message", () => {
    expect(
      mapSubmitErrors("Bandwidth exceeds the site capacity at bandwidth", ["site", "bandwidth"])
        .fieldErrors
    ).toEqual({ bandwidth: "Bandwidth exceeds the site capacity at bandwidth" });
  });

  test("maps a resource pool key to its field", () => {
    expect(
      mapSubmitErrors("pool exhausted at vlan_from_resource_pool", ["vlan"]).fieldErrors
    ).toEqual({
      vlan: "pool exhausted at vlan_from_resource_pool",
    });
  });

  test("does not match a field name inside a longer word", () => {
    expect(mapSubmitErrors("hostname is invalid", ["name"])).toEqual({
      fieldErrors: {},
      formError: "hostname is invalid",
    });
  });

  test("splits joined messages between fields and the form", () => {
    expect(mapSubmitErrors("too long at name; Service is disabled", ["name"])).toEqual({
      fieldErrors: { name: "too long at name" },
      formError: "Service is disabled",
    });
  });
});
