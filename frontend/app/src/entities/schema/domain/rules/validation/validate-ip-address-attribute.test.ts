import { describe, expect, it } from "vitest";

import { validateIpAddressAttribute } from "./validate-ip-address-attribute";

describe("validateIpAddressAttribute", () => {
  it.each([
    "10.0.0.1",
    "0.0.0.0",
    "255.255.255.255",
    "2001:db8::1",
    "::1",
    "::ffff:10.0.0.1",
  ])("accepts the bare address %s", (value) => {
    expect(validateIpAddressAttribute({}, value)).toEqual({ success: true, data: value });
  });

  it.each([
    "10.0.0.1/32",
    "10.0.0.1/24",
    "10.0.0.0/255.255.255.0",
    "2001:db8::1/128",
  ])("rejects %s for carrying a prefix", (value) => {
    expect(validateIpAddressAttribute({}, value)).toEqual({
      success: false,
      error: "Must be a bare IP address, without a prefix or netmask",
    });
  });

  it.each([
    "010.0.0.1",
    "10.0.0.256",
    "10.0.1",
    "not-an-ip",
    "2001:db8::1::2",
    "12345::1",
  ])("rejects %s as malformed", (value) => {
    expect(validateIpAddressAttribute({}, value)).toEqual({
      success: false,
      error: "Must be a valid IPv4 or IPv6 address",
    });
  });

  it("treats an empty value as valid when the attribute is optional", () => {
    expect(validateIpAddressAttribute({}, "")).toEqual({ success: true, data: "" });
    expect(validateIpAddressAttribute({}, null)).toEqual({ success: true, data: "" });
  });

  it("requires a value when the attribute is mandatory", () => {
    expect(validateIpAddressAttribute({ isRequired: true }, "")).toEqual({
      success: false,
      error: "Required",
    });
  });
});
