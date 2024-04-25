export const IP_ADDRESS_GENERIC = "BuiltinIPAddress";
export const IP_PREFIX_GENERIC = "BuiltinIPPrefix";

export const IPAM_TREE_ROOT_ID = "root" as const;

export const IPAM_TABS = {
  SUMMARY: "summary",
  PREFIX_DETAILS: "prefix-details",
  IP_DETAILS: "ip-details",
};

const IPAM_ROOT_ROUTE = "/ipam";

export const IPAM_ROUTE = {
  ROOT: IPAM_ROOT_ROUTE,
  ADDRESSES: `${IPAM_ROOT_ROUTE}/addresses`,
  PREFIXES: `${IPAM_ROOT_ROUTE}/prefixes`,
} as const;

export const IPAM_QSP = "ipam-tab";
