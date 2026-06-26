import type { IpPoolSource, NumberPoolSource, PoolSource } from "@/shared/components/form/type";

import { NUMBER_POOL_KIND } from "@/entities/resource-manager/constants";

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

  // A non-number pool kind is an IP pool.
  const source: IpPoolSource = { type: "pool", id, label, kind: kind as IpPoolSource["kind"] };
  if (fromTemplate) source.fromTemplate = true;
  if (defaultPrefixLength !== undefined) source.defaultPrefixLength = defaultPrefixLength;
  return source;
};
