import { IP_ADDRESS_GENERIC } from "@/entities/ipam/ip-addresses/domain/model/ip-address";
import { IP_PREFIX_GENERIC } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
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
