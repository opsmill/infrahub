import { describe, expect, it } from "vitest";

import { parsePrefixLength } from "@/entities/ipam/ip-prefixes/domain/rules/parse-prefix-length";

describe("parsePrefixLength", () => {
  it("parses an IPv4 prefix into its family, length and address count", () => {
    // GIVEN
    const cidr = "10.0.0.0/8";

    // WHEN
    const result = parsePrefixLength(cidr);

    // THEN
    expect(result).toEqual({ family: "ipv4", prefixLength: 8, addressCount: 16777216n });
  });

  it("parses an IPv6 prefix into its family, length and address count", () => {
    // GIVEN
    const cidr = "2001:db8::/32";

    // WHEN
    const result = parsePrefixLength(cidr);

    // THEN
    expect(result).toEqual({ family: "ipv6", prefixLength: 32, addressCount: 2n ** 96n });
  });

  it("gives the full IPv6 space for a zero-length prefix", () => {
    // GIVEN
    const cidr = "::/0";

    // WHEN
    const result = parsePrefixLength(cidr);

    // THEN
    expect(result).toEqual({ family: "ipv6", prefixLength: 0, addressCount: 2n ** 128n });
  });

  it("gives the full IPv4 space for a zero-length prefix", () => {
    // GIVEN
    const cidr = "0.0.0.0/0";

    // WHEN
    const result = parsePrefixLength(cidr);

    // THEN
    expect(result).toEqual({ family: "ipv4", prefixLength: 0, addressCount: 2n ** 32n });
  });

  it("throws when an IPv4 prefix length exceeds 32", () => {
    // GIVEN
    const cidr = "10.0.0.0/33";

    // WHEN
    const parse = () => parsePrefixLength(cidr);

    // THEN
    expect(parse).toThrow("10.0.0.0/33");
  });

  it("throws when an IPv6 prefix length exceeds 128", () => {
    // GIVEN
    const cidr = "2001:db8::/129";

    // WHEN
    const parse = () => parsePrefixLength(cidr);

    // THEN
    expect(parse).toThrow("2001:db8::/129");
  });

  it("throws when the string has no slash", () => {
    // GIVEN
    const cidr = "10.0.0.0";

    // WHEN
    const parse = () => parsePrefixLength(cidr);

    // THEN
    expect(parse).toThrow("10.0.0.0");
  });

  it("throws when the string is empty", () => {
    // GIVEN
    const cidr = "";

    // WHEN
    const parse = () => parsePrefixLength(cidr);

    // THEN
    expect(parse).toThrow(Error);
  });
});
