import { RELATIONSHIP_VIEW_BLACKLIST } from "@/config/constants";

export const NAMESPACE_GENERIC = "BuiltinIPNamespace";
export const IP_ADDRESS_GENERIC = "BuiltinIPAddress";
export const IP_PREFIX_GENERIC = "BuiltinIPPrefix";
export const POOLS_PEER = [IP_ADDRESS_GENERIC, IP_PREFIX_GENERIC];
export const POOLS_DICTIONNARY = {
  IpamIPAddress: "CoreIPAddressPool",
  IpamIPPrefix: "CoreIPPrefixPool",
};

export const TREE_ROOT_ID = "root" as const;

export const IPAM_TABS = {
  SUMMARY: "summary",
  PREFIX_DETAILS: "prefix-details",
  IP_DETAILS: "ip-details",
};

const IPAM_BASE_ROUTE = "/ipam";

export const IPAM_ROUTE = {
  INDEX: IPAM_BASE_ROUTE,
  ADDRESSES: `${IPAM_BASE_ROUTE}/addresses`,
  PREFIXES: `${IPAM_BASE_ROUTE}/prefixes`,
} as const;

export const IPAM_QSP = {
  TAB: "ipam-tab",
  NAMESPACE: "namespace",
};

export const IP_SUMMARY_RELATIONSHIPS_BLACKLIST = [...RELATIONSHIP_VIEW_BLACKLIST, "ip_addresses"];
