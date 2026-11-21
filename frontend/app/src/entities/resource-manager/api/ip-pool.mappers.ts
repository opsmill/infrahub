import type {
  IpAddressPoolNode,
  IpPrefixPoolNode,
} from "@/entities/resource-manager/api/get-ip-pool-from-api";
import {
  IP_POOL_MEMBER_TYPE_ADDRESS,
  IP_POOL_MEMBER_TYPE_PREFIX,
  type IpAddressPoolData,
  type IpPoolNamespace,
  type IpPrefixPoolData,
} from "@/entities/resource-manager/domain/model/ip-pool";
import { IP_ADDRESS_POOL, IP_PREFIX_POOL } from "@/entities/resource-manager/domain/model/pool";

type NamespaceNode = IpPrefixPoolNode["ip_namespace"]["node"];

const mapToNamespace = (node: NamespaceNode): IpPoolNamespace => ({
  id: node?.id ?? "",
  display_label: node?.display_label ?? "",
  isDefault: node !== null && "default" in node && node.default?.value === true,
});

const mapCommonFields = (node: IpPrefixPoolNode | IpAddressPoolNode) => ({
  id: node.id,
  hfid: node.hfid,
  display_label: node.display_label,
  name: { value: node.name?.value ?? "" },
  description: { value: node.description?.value || null },
  default_prefix_length: { value: node.default_prefix_length?.value ?? null },
  ip_namespace: mapToNamespace(node.ip_namespace.node),
});

const toMemberType = (value: string | null | undefined) =>
  value === IP_POOL_MEMBER_TYPE_PREFIX || value === IP_POOL_MEMBER_TYPE_ADDRESS ? value : null;

export const mapToIpPrefixPoolData = (node: IpPrefixPoolNode): IpPrefixPoolData => ({
  ...mapCommonFields(node),
  __typename: IP_PREFIX_POOL,
  default_prefix_type: { value: node.default_prefix_type?.value || null },
  default_member_type: { value: toMemberType(node.default_member_type?.value) },
});

export const mapToIpAddressPoolData = (node: IpAddressPoolNode): IpAddressPoolData => ({
  ...mapCommonFields(node),
  __typename: IP_ADDRESS_POOL,
  default_address_type: { value: node.default_address_type?.value || null },
});
