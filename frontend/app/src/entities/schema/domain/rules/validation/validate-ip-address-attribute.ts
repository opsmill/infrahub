const IPV4_PATTERN = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/;

function isValidIpv4(value: string): boolean {
  const match = IPV4_PATTERN.exec(value);
  if (!match) return false;

  return match.slice(1).every((octet) => {
    // a leading zero is ambiguous between decimal and octal, so the backend rejects it too
    if (octet.length > 1 && octet.startsWith("0")) return false;
    return Number(octet) <= 255;
  });
}

const HEX_GROUP = /^[0-9a-fA-F]{1,4}$/;

function isValidIpv6(value: string): boolean {
  // At most one "::" run, and it is what allows fewer than the full eight groups.
  const runs = value.split("::");
  if (runs.length > 2) return false;
  const isCompressed = runs.length === 2;

  const head = runs[0] ?? "";
  const tail = runs[1] ?? "";
  const headParts = head === "" ? [] : head.split(":");
  const tailParts = tail === "" ? [] : tail.split(":");
  const parts = [...headParts, ...tailParts];

  const last = parts.at(-1);
  const endsWithDottedQuad = last !== undefined && !HEX_GROUP.test(last);
  if (endsWithDottedQuad && !isValidIpv4(last)) return false;

  const hexParts = endsWithDottedQuad ? parts.slice(0, -1) : parts;
  if (hexParts.some((part) => !HEX_GROUP.test(part))) return false;

  // A trailing dotted quad carries 32 bits, so it stands for the final two groups.
  const groupCount = parts.length + (endsWithDottedQuad ? 1 : 0);

  // "::" stands for at least one group of zeros, so the explicit groups must leave room for it.
  return isCompressed ? groupCount <= 7 : groupCount === 8;
}

export function validateIpAddressAttribute(
  { isRequired = false }: { isRequired?: boolean },
  value: string | null | undefined
): { success: true; data: string } | { success: false; error: string } {
  if (!value) {
    return isRequired ? { success: false, error: "Required" } : { success: true, data: "" };
  }

  if (value.includes("/")) {
    return {
      success: false,
      error: "Must be a bare IP address, without a prefix or netmask",
    };
  }

  if (!isValidIpv4(value) && !isValidIpv6(value)) {
    return { success: false, error: "Must be a valid IPv4 or IPv6 address" };
  }

  return { success: true, data: value };
}
