import { describe, expect, it } from "vitest";

import {
  generateIpAddressPoolData,
  generateIpPrefixPoolData,
} from "../../../../../tests/fake/ip-pool";
import { getIpPoolDefaultEntries } from "./get-ip-pool-default-entries";

describe("getIpPoolDefaultEntries", () => {
  it("reads the prefix kind, the prefix length and the member type of a prefix pool", () => {
    // GIVEN
    const pool = generateIpPrefixPoolData();

    // WHEN
    const entries = getIpPoolDefaultEntries(pool);

    // THEN
    expect(entries).toEqual([
      {
        label: "Prefix kind",
        value: { type: "kind", kind: "IpamIPPrefix" },
        fallbackPhrase: "has no default",
      },
      {
        label: "Prefix length",
        value: { type: "prefix-length", length: 31 },
        fallbackPhrase: "has no default",
      },
      {
        label: "Member type",
        value: { type: "member-type", memberType: "address" },
        fallbackPhrase: "has no default",
      },
    ]);
  });

  it("reads the address kind and the prefix length of an address pool", () => {
    // GIVEN
    const pool = generateIpAddressPoolData();

    // WHEN
    const entries = getIpPoolDefaultEntries(pool);

    // THEN
    expect(entries).toEqual([
      {
        label: "Address kind",
        value: { type: "kind", kind: "IpamIPAddress" },
        fallbackPhrase: "has no default",
      },
      {
        label: "Prefix length",
        value: { type: "prefix-length", length: 32 },
        fallbackPhrase: "follows the resource prefix",
      },
    ]);
  });

  it("leaves every value empty when a prefix pool sets no default", () => {
    // GIVEN
    const pool = generateIpPrefixPoolData({
      default_prefix_type: { value: null },
      default_prefix_length: { value: null },
      default_member_type: { value: null },
    });

    // WHEN
    const entries = getIpPoolDefaultEntries(pool);

    // THEN
    expect(entries.map(({ value }) => value)).toEqual([null, null, null]);
  });

  it("says the prefix length of an address pool follows the resource prefix when it is not set", () => {
    // GIVEN
    const pool = generateIpAddressPoolData({ default_prefix_length: { value: null } });

    // WHEN
    const [, length] = getIpPoolDefaultEntries(pool);

    // THEN
    expect(length).toEqual({
      label: "Prefix length",
      value: null,
      fallbackPhrase: "follows the resource prefix",
    });
  });
});
