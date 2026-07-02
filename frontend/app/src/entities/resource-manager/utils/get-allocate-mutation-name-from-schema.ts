import { IP_ADDRESS_GENERIC, IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import type { ModelSchema } from "@/entities/schema/domain/model/types";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";

export function getAllocateMutationNameFromSchema(schema: ModelSchema) {
  if (isOfKind(IP_ADDRESS_GENERIC, schema)) {
    return "InfrahubIPAddressPoolGetResource";
  }

  if (isOfKind(IP_PREFIX_GENERIC, schema)) {
    return "InfrahubIPPrefixPoolGetResource";
  }

  return null;
}
