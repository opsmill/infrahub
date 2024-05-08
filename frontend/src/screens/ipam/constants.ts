export const IP_ADDRESS_GENERIC = "BuiltinIPAddress";
export const IP_PREFIX_GENERIC = "BuiltinIPPrefix";

export const IPAM_TREE_ROOT_ID = "root" as const;

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

export const IPAM_QSP = "ipam-tab";

export const IP_SUMMARY_RELATIONSHIPS_BLACKLIST = [
  "ip_addresses",
  "member_of_groups",
  "subscriber_of_groups",
  "children",
  "profiles",
];
