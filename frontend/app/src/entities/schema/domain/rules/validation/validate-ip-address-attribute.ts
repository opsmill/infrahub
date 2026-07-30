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

function isValidIpv6(value: string): boolean {
  // Only one "::" run may appear, and it is what allows fewer than 8 groups.
  const doubleColonCount = value.split("::").length - 1;
  if (doubleColonCount > 1) return false;

  const parts = value.split("::");
  const head = parts[0] ?? "";
  const tail = parts[1] ?? "";
  const headGroups = head === "" ? [] : head.split(":");
  const tailGroups = tail === "" ? [] : tail.split(":");
  const groups = [...headGroups, ...tailGroups];

  if (groups.some((group) => !/^[0-9a-fA-F]{1,4}$/.test(group))) {
    // the last group may be a dotted-quad, as in an IPv4-mapped address
    const last = groups.at(-1);
    if (!last || !isValidIpv4(last)) return false;
    if (groups.slice(0, -1).some((group) => !/^[0-9a-fA-F]{1,4}$/.test(group))) return false;
  }

  return doubleColonCount === 1 ? groups.length <= 8 : groups.length === 8;
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
