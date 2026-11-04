import {
  IP_POOL_MEMBER_TYPE_ADDRESS,
  IP_POOL_MEMBER_TYPE_PREFIX,
  type IpPoolData,
  type IpPoolDefaultEntry,
} from "@/entities/resource-manager/domain/model/ip-pool";
import { IP_ADDRESS_POOL } from "@/entities/resource-manager/domain/model/pool";

const NO_DEFAULT = "has no default";

const toMemberType = (value: string | null) =>
  value === IP_POOL_MEMBER_TYPE_PREFIX || value === IP_POOL_MEMBER_TYPE_ADDRESS ? value : null;

export const getIpPoolDefaultEntries = (pool: IpPoolData): IpPoolDefaultEntry[] => {
  const length = pool.default_prefix_length.value;
  const lengthValue = length === null ? null : { type: "prefix-length" as const, length };

  if (pool.__typename === IP_ADDRESS_POOL) {
    const kind = pool.default_address_type.value;
    return [
      {
        label: "Address kind",
        value: kind ? { type: "kind", kind } : null,
        fallbackPhrase: NO_DEFAULT,
      },
      {
        label: "Prefix length",
        value: lengthValue,
        fallbackPhrase: "follows the resource prefix",
      },
    ];
  }

  const kind = pool.default_prefix_type.value;
  const memberType = toMemberType(pool.default_member_type.value);
  return [
    {
      label: "Prefix kind",
      value: kind ? { type: "kind", kind } : null,
      fallbackPhrase: NO_DEFAULT,
    },
    { label: "Prefix length", value: lengthValue, fallbackPhrase: NO_DEFAULT },
    {
      label: "Member type",
      value: memberType ? { type: "member-type", memberType } : null,
      fallbackPhrase: NO_DEFAULT,
    },
  ];
};
