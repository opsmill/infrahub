import { RELATIONSHIP_VIEW_BLACKLIST } from "@/config/constants";
import { IP_ADDRESS_POOL, IP_PREFIX_POOL } from "../resource-manager/constants";

export const IP_NAMESPACE_GENERIC = "BuiltinIPNamespace";
export const IP_ADDRESS_GENERIC = "BuiltinIPAddress";
export const IP_PREFIX_GENERIC = "BuiltinIPPrefix";

export const POOLS_PEER = [IP_ADDRESS_GENERIC, IP_PREFIX_GENERIC];
export const POOLS_DICTIONNARY = {
  IpamIPAddress: IP_ADDRESS_POOL,
  IpamIPPrefix: IP_PREFIX_POOL,
};

export const TREE_ROOT_ID = "root" as const;

export const IPAM_QSP = {
  NAMESPACE: "namespace",
};

export const IP_SUMMARY_RELATIONSHIPS_BLACKLIST = [...RELATIONSHIP_VIEW_BLACKLIST, "ip_addresses"];
