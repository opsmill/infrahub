import type {
  IpFamily,
  PrefixSize,
} from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map";

const MAX_PREFIX_LENGTH: Record<IpFamily, number> = { ipv4: 32, ipv6: 128 };

export interface PrefixFields {
  cidr: string;
  prefixLength: number;
  version: number;
}

export function familyFromVersion(version: number): IpFamily {
  if (version === 4) return "ipv4";
  if (version === 6) return "ipv6";
  throw new Error(`Unsupported IP version ${version}`);
}

export function maxPrefixLength(family: IpFamily): number {
  return MAX_PREFIX_LENGTH[family];
}

function parseIpv4(address: string): bigint {
  const octets = address.split(".");
  if (octets.length !== 4) throw new Error(`Invalid IPv4 address "${address}"`);
  return octets.reduce((value, octet) => {
    if (!/^\d{1,3}$/.test(octet) || Number(octet) > 255) {
      throw new Error(`Invalid IPv4 address "${address}"`);
    }
    return value * 256n + BigInt(octet);
  }, 0n);
}

function parseHextets(part: string, address: string): bigint[] {
  if (part === "") return [];
  return part.split(":").map((hextet) => {
    if (!/^[0-9a-fA-F]{1,4}$/.test(hextet)) throw new Error(`Invalid IPv6 address "${address}"`);
    return BigInt(`0x${hextet}`);
  });
}

function parseIpv6(address: string): bigint {
  let text = address;
  let tail: bigint[] = [];
  // An embedded IPv4 suffix supplies the last two hextets.
  const lastColon = text.lastIndexOf(":");
  if (text.includes(".") && lastColon !== -1) {
    const ipv4 = parseIpv4(text.slice(lastColon + 1));
    tail = [ipv4 / 65536n, ipv4 % 65536n];
    text = text.slice(0, lastColon);
    // A bare ":" left behind means the address started with a compressed run.
    if (text.endsWith(":")) text += ":";
  }

  const halves = text.split("::");
  if (halves.length > 2) throw new Error(`Invalid IPv6 address "${address}"`);
  const head = parseHextets(halves[0] ?? "", address);
  const rest = halves.length === 2 ? parseHextets(halves[1] ?? "", address) : [];
  const explicit = head.length + rest.length + tail.length;
  if (explicit > 8 || (halves.length === 1 && explicit !== 8)) {
    throw new Error(`Invalid IPv6 address "${address}"`);
  }
  const zeros = new Array<bigint>(8 - explicit).fill(0n);
  return [...head, ...zeros, ...rest, ...tail].reduce(
    (value, hextet) => value * 65536n + hextet,
    0n
  );
}

/** Parses the address part of a CIDR string into an integer, before masking. */
export function parseAddress(cidr: string, family: IpFamily): bigint {
  const address = cidr.split("/")[0] ?? "";
  return family === "ipv4" ? parseIpv4(address) : parseIpv6(address);
}

/** Builds the exact block a prefix covers from the fields the API exposes on an IPNetwork. */
export function buildPrefixSize({ cidr, prefixLength, version }: PrefixFields): PrefixSize {
  const family = familyFromVersion(version);
  const maxLength = maxPrefixLength(family);
  if (!Number.isInteger(prefixLength) || prefixLength < 0 || prefixLength > maxLength) {
    throw new Error(`Invalid prefix length ${prefixLength} for ${cidr}`);
  }
  const addressCount = 2n ** BigInt(maxLength - prefixLength);
  // Masking tolerates a host address in the string; the block starts at its network address.
  const networkAddress = (parseAddress(cidr, family) / addressCount) * addressCount;
  return { family, prefixLength, networkAddress, addressCount };
}

export function blockEnd(size: PrefixSize): bigint {
  return size.networkAddress + size.addressCount;
}

function formatIpv4(address: bigint): string {
  const octets: string[] = [];
  let value = address;
  for (let index = 0; index < 4; index += 1) {
    octets.unshift(String(value % 256n));
    value /= 256n;
  }
  return octets.join(".");
}

function formatIpv6(address: bigint): string {
  const hextets: number[] = [];
  let value = address;
  for (let index = 0; index < 8; index += 1) {
    hextets.unshift(Number(value % 65536n));
    value /= 65536n;
  }
  // Compress the longest run of zero hextets, as the backend's string form does.
  let bestStart = -1;
  let bestLength = 0;
  for (let start = 0; start < 8; start += 1) {
    if (hextets[start] !== 0) continue;
    let end = start;
    while (end < 8 && hextets[end] === 0) end += 1;
    if (end - start > bestLength) {
      bestStart = start;
      bestLength = end - start;
    }
  }
  const text = hextets.map((hextet) => hextet.toString(16));
  if (bestLength < 2) return text.join(":");
  const head = text.slice(0, bestStart).join(":");
  const rest = text.slice(bestStart + bestLength).join(":");
  return `${head}::${rest}`;
}

/** Formats a block as the CIDR string the rest of the product shows. */
export function formatCidr(size: PrefixSize): string {
  const address =
    size.family === "ipv4" ? formatIpv4(size.networkAddress) : formatIpv6(size.networkAddress);
  return `${address}/${size.prefixLength}`;
}

/** The aligned block of `prefixLength` bits that contains `address`. */
export function containingBlock(
  address: bigint,
  prefixLength: number,
  family: IpFamily
): PrefixSize {
  const addressCount = 2n ** BigInt(maxPrefixLength(family) - prefixLength);
  return {
    family,
    prefixLength,
    networkAddress: (address / addressCount) * addressCount,
    addressCount,
  };
}

/** Splits an address range into the fewest aligned CIDR blocks, in address order. */
export function rangeToBlocks(start: bigint, end: bigint, family: IpFamily): PrefixSize[] {
  const maxLength = maxPrefixLength(family);
  const blocks: PrefixSize[] = [];
  let cursor = start;
  while (cursor < end) {
    let addressCount = 1n;
    // Grow the block while it stays aligned to its own size and inside the range.
    while (
      addressCount * 2n <= end - cursor &&
      cursor % (addressCount * 2n) === 0n &&
      addressCount * 2n <= 2n ** BigInt(maxLength)
    ) {
      addressCount *= 2n;
    }
    const prefixLength = maxLength - addressCount.toString(2).length + 1;
    blocks.push({ family, prefixLength, networkAddress: cursor, addressCount });
    cursor += addressCount;
  }
  return blocks;
}
