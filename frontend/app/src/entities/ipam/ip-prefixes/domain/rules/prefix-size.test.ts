import { describe, expect, it } from "vitest";

import {
  blockEnd,
  buildPrefixSize,
  containingBlock,
  formatCidr,
  parseAddress,
  rangeToBlocks,
} from "@/entities/ipam/ip-prefixes/domain/rules/prefix-size";

describe("buildPrefixSize", () => {
  it("builds an IPv4 block from the API fields", () => {
    // GIVEN the fields of 10.1.0.0/16
    // WHEN the block is built
    const size = buildPrefixSize({ cidr: "10.1.0.0/16", prefixLength: 16, version: 4 });

    // THEN its family, length, start and extent are exact
    expect(size).toEqual({
      family: "ipv4",
      prefixLength: 16,
      networkAddress: 10n * 2n ** 24n + 1n * 2n ** 16n,
      addressCount: 65536n,
    });
  });

  it("builds an IPv6 block with an address count beyond the double range", () => {
    // GIVEN the fields of 2001:db8::/32
    // WHEN the block is built
    const size = buildPrefixSize({ cidr: "2001:db8::/32", prefixLength: 32, version: 6 });

    // THEN the count is 2^96 and the start is the expanded address
    expect(size.family).toBe("ipv6");
    expect(size.addressCount).toBe(2n ** 96n);
    expect(size.networkAddress).toBe(0x20010db8n * 2n ** 96n);
  });

  it("masks a host address down to its network address", () => {
    // GIVEN a CIDR string whose address is inside the block, not at its start
    // WHEN the block is built
    const size = buildPrefixSize({ cidr: "10.1.2.3/16", prefixLength: 16, version: 4 });

    // THEN the block starts at 10.1.0.0
    expect(formatCidr(size)).toBe("10.1.0.0/16");
  });

  it("rejects a prefix length outside the family range", () => {
    // GIVEN an IPv4 prefix length of 33
    // WHEN the block is built
    // THEN it throws
    expect(() => buildPrefixSize({ cidr: "10.0.0.0/33", prefixLength: 33, version: 4 })).toThrow();
  });

  it("rejects an unknown IP version", () => {
    // GIVEN a version of 5
    // WHEN the block is built
    // THEN it throws
    expect(() => buildPrefixSize({ cidr: "10.0.0.0/8", prefixLength: 8, version: 5 })).toThrow();
  });
});

describe("parseAddress", () => {
  it("parses the full IPv4 address space", () => {
    // GIVEN the last IPv4 address
    // WHEN it is parsed
    // THEN it is 2^32 - 1
    expect(parseAddress("255.255.255.255/32", "ipv4")).toBe(2n ** 32n - 1n);
  });

  it("expands a compressed IPv6 address", () => {
    // GIVEN an address with a :: run in the middle
    // WHEN it is parsed
    // THEN the run expands to zero hextets
    expect(parseAddress("fd00:1000::1/128", "ipv6")).toBe(0xfd001000n * 2n ** 96n + 1n);
  });

  it("parses an IPv6 address with an embedded IPv4 suffix", () => {
    // GIVEN an IPv4-mapped IPv6 address
    // WHEN it is parsed
    // THEN the last 32 bits hold the IPv4 address
    expect(parseAddress("::ffff:192.0.2.1/128", "ipv6")).toBe(0xffffn * 2n ** 32n + 0xc0000201n);
  });

  it("rejects an address with too many hextets", () => {
    // GIVEN nine hextets
    // WHEN it is parsed
    // THEN it throws
    expect(() => parseAddress("1:2:3:4:5:6:7:8:9/128", "ipv6")).toThrow();
  });
});

describe("formatCidr", () => {
  it("compresses the longest zero run of an IPv6 block", () => {
    // GIVEN a block with zero hextets in the middle
    const size = buildPrefixSize({
      cidr: "2001:db8:0:0:0:0:0:0/100",
      prefixLength: 100,
      version: 6,
    });

    // WHEN it is formatted
    // THEN the zero run becomes ::
    expect(formatCidr(size)).toBe("2001:db8::/100");
  });
});

describe("containingBlock", () => {
  it("returns the aligned block of the given length around an address", () => {
    // GIVEN an address inside 10.0.4.0/22
    const address = parseAddress("10.0.5.9/32", "ipv4");

    // WHEN the /22 containing it is computed
    const block = containingBlock(address, 22, "ipv4");

    // THEN it starts at 10.0.4.0
    expect(formatCidr(block)).toBe("10.0.4.0/22");
  });
});

describe("rangeToBlocks", () => {
  it("splits a range into the fewest aligned blocks in address order", () => {
    // GIVEN the range from 10.0.3.0 to the end of 10.0.0.0/16
    const start = parseAddress("10.0.3.0/32", "ipv4");
    const end = blockEnd(buildPrefixSize({ cidr: "10.0.0.0/16", prefixLength: 16, version: 4 }));

    // WHEN it is decomposed
    const blocks = rangeToBlocks(start, end, "ipv4").map(formatCidr);

    // THEN the blocks grow as alignment allows and cover the range exactly once
    expect(blocks).toEqual([
      "10.0.3.0/24",
      "10.0.4.0/22",
      "10.0.8.0/21",
      "10.0.16.0/20",
      "10.0.32.0/19",
      "10.0.64.0/18",
      "10.0.128.0/17",
    ]);
  });

  it("returns nothing for an empty range", () => {
    // GIVEN a range with no addresses
    // WHEN it is decomposed
    // THEN there are no blocks
    expect(rangeToBlocks(10n, 10n, "ipv4")).toEqual([]);
  });
});
