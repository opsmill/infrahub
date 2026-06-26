import type { IpPoolSource, NumberPoolSource, PoolSource } from "@/shared/components/form/type";

import {
  IP_ADDRESS_POOL,
  IP_PREFIX_POOL,
  NUMBER_POOL_KIND,
} from "@/entities/resource-manager/constants";

/** Build a discriminated PoolSource, narrowing the raw pool `__typename` to a PoolKind. */
export const makePoolSource = ({
  id,
  kind,
  label,
  fromTemplate,
  defaultPrefixLength,
}: {
  id: string;
  kind: string;
  label: string | null;
  fromTemplate?: boolean;
  defaultPrefixLength?: number | null;
}): PoolSource => {
  if (kind === NUMBER_POOL_KIND) {
    const source: NumberPoolSource = { type: "pool", id, label, kind };
    if (fromTemplate) source.fromTemplate = true;
    return source;
  }

  // Address and prefix pools both support the prefix-length override; the from-pool list
  // only ever surfaces these three kinds, so anything else falls back to IP address.
  const ipKind = kind === IP_PREFIX_POOL ? IP_PREFIX_POOL : IP_ADDRESS_POOL;
  const source: IpPoolSource = { type: "pool", id, label, kind: ipKind };
  if (fromTemplate) source.fromTemplate = true;
  if (defaultPrefixLength !== undefined) source.defaultPrefixLength = defaultPrefixLength;
  return source;
};
