import type { IpPoolSource, NumberPoolSource, PoolSource } from "@/shared/components/form/type";

import { NUMBER_POOL_KIND } from "@/entities/resource-manager/constants";

/**
 * Build a discriminated {@link PoolSource} from a raw pool `__typename`. This is the single
 * place that narrows the kind string to a `PoolKind`, so every from-pool source construction
 * (default values, template/profile fallbacks, fresh selections) gets the precise per-kind
 * shape without each call site repeating the narrowing.
 *
 * `defaultPrefixLength` only applies to IP pools and is kept only when explicitly provided —
 * callers loading an existing value omit it, matching the prior behaviour.
 */
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

  // The from-pool list only ever surfaces pool kinds, so a non-number kind is an IP pool.
  const source: IpPoolSource = { type: "pool", id, label, kind: kind as IpPoolSource["kind"] };
  if (fromTemplate) source.fromTemplate = true;
  if (defaultPrefixLength !== undefined) source.defaultPrefixLength = defaultPrefixLength;
  return source;
};
