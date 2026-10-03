import type { PrefixSize } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map";

const IPV4_MAX_PREFIX_LENGTH = 32;
const IPV6_MAX_PREFIX_LENGTH = 128;

/**
 * Derives the address family, prefix length and exact address count of a CIDR string.
 *
 * Only the prefix length is validated; the backend owns the validity of the address part.
 * Throws an `Error` naming the input when the string has no `/`, a non-integer length, or a
 * length outside the family's range.
 */
export function parsePrefixLength(cidr: string): PrefixSize {
  const slashIndex = cidr.lastIndexOf("/");
  if (slashIndex === -1) {
    throw new Error(`Invalid CIDR "${cidr}": missing prefix length`);
  }

  const family: PrefixSize["family"] = cidr.includes(":") ? "ipv6" : "ipv4";
  const maxLength = family === "ipv6" ? IPV6_MAX_PREFIX_LENGTH : IPV4_MAX_PREFIX_LENGTH;

  const lengthText = cidr.slice(slashIndex + 1);
  if (!/^\d+$/.test(lengthText)) {
    throw new Error(`Invalid CIDR "${cidr}": prefix length is not an integer`);
  }

  const prefixLength = Number(lengthText);
  if (prefixLength > maxLength) {
    throw new Error(`Invalid CIDR "${cidr}": prefix length exceeds ${maxLength} for ${family}`);
  }

  return {
    family,
    prefixLength,
    addressCount: 2n ** BigInt(maxLength - prefixLength),
  };
}
