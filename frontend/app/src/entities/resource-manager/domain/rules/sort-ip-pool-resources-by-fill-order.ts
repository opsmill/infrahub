import type { IpPoolResource } from "@/entities/resource-manager/domain/model/ip-pool";

type ParsedPrefix = { version: 4 | 6; network: bigint; length: number };

const parseIpv4 = (address: string): bigint | null => {
  const octets = address.split(".");
  if (octets.length !== 4) return null;
  let value = 0n;
  for (const octet of octets) {
    if (!/^\d{1,3}$/.test(octet) || Number(octet) > 255) return null;
    value = value * 256n + BigInt(octet);
  }
  return value;
};

const parseIpv6 = (address: string): bigint | null => {
  const halves = address.split("::");
  if (halves.length > 2) return null;
  const toGroups = (part: string | undefined) => (part ? part.split(":") : []);
  const head = toGroups(halves[0]);
  const tail = toGroups(halves[1]);
  const missing = 8 - head.length - tail.length;
  if (halves.length === 1 ? missing !== 0 : missing < 1) return null;
  const groups = [...head, ...Array<string>(halves.length === 1 ? 0 : missing).fill("0"), ...tail];
  let value = 0n;
  for (const group of groups) {
    if (!/^[0-9a-f]{1,4}$/i.test(group)) return null;
    value = value * 65536n + BigInt(`0x${group}`);
  }
  return value;
};

const parsePrefix = (label: string): ParsedPrefix | null => {
  const [address, length, ...rest] = label.split("/");
  if (!address || !length || rest.length > 0 || !/^\d+$/.test(length)) return null;
  const ipv4 = parseIpv4(address);
  if (ipv4 !== null) return { version: 4, network: ipv4, length: Number(length) };
  const ipv6 = parseIpv6(address);
  if (ipv6 !== null) return { version: 6, network: ipv6, length: Number(length) };
  return null;
};

const compareBigInt = (a: bigint, b: bigint) => (a < b ? -1 : a > b ? 1 : 0);

const compareByPrefix = (a: IpPoolResource, b: IpPoolResource): number => {
  const prefixA = parsePrefix(a.display_label);
  const prefixB = parsePrefix(b.display_label);
  if (!prefixA || !prefixB) {
    return a.display_label.localeCompare(b.display_label, undefined, { numeric: true });
  }
  return (
    prefixA.version - prefixB.version ||
    compareBigInt(prefixA.network, prefixB.network) ||
    prefixA.length - prefixB.length
  );
};

const weightOf = (resource: IpPoolResource) => resource.allocationWeight ?? 0;

// The server fills the heaviest resource prefix first and defines no order between equal weights, so ties are ordered by prefix.
export const sortIpPoolResourcesByFillOrder = (resources: IpPoolResource[]): IpPoolResource[] =>
  [...resources].sort((a, b) => weightOf(b) - weightOf(a) || compareByPrefix(a, b));
