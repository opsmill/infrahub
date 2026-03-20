import type { Filter } from "@/shared/hooks/useFilters";

export const IP_NAMESPACE_GENERIC = "BuiltinIPNamespace";
export const IP_NAMESPACE_KIND = "IpamNamespace";
export const IP_ADDRESS_GENERIC = "BuiltinIPAddress";
export const IP_ADDRESS_AVAILABLE_KIND = "InternalIPRangeAvailable" as const;
export const IP_PREFIX_GENERIC = "BuiltinIPPrefix";
export const IP_PREFIX_AVAILABLE_KIND = "InternalIPPrefixAvailable";

export const IP_PREFIX_RELATIONSHIP_NAME = "ip_prefix";

export const IPAM_QSP = {
  NAMESPACE: "namespace",
};

export const IP_SUMMARY_RELATIONSHIPS_BLACKLIST = [
  "member_of_groups",
  "subscriber_of_groups",
  "children",
  "profiles",
  "ip_addresses",
];

// Filter related
export const AVAILABLE_IP_FILTER_NAME = "include_available" as const;
export const HIDE_AVAILABLE_IP_FILTER: Filter = { name: AVAILABLE_IP_FILTER_NAME, value: false };
export const HIDE_AVAILABLE_IP = "hide-available-ip";
export const SHOW_AVAILABLE_IP = "show-available-ip";

export const IPAM_TREE_KEY = "ipam_tree_collapsed";
