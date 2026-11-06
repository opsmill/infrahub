import { IP_PREFIX_GENERIC } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix";
import { ALLOCATION_WEIGHT_ATTRIBUTE } from "@/entities/resource-manager/domain/model/ip-pool";
import type { NodeSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";

export const getWeightedPrefixKinds = (schemas: NodeSchema[]): string[] =>
  schemas
    .filter(
      (schema) =>
        isOfKind(IP_PREFIX_GENERIC, schema) &&
        schema.attributes?.some(({ name }) => name === ALLOCATION_WEIGHT_ATTRIBUTE)
    )
    .map((schema) => schema.kind as string)
    .sort();
