import { FROM_RESOURCE_POOL_SUFFIX } from "@/shared/components/form/constants";

export function isFromResourcePoolRelationship(name: string): boolean {
  return name.endsWith(FROM_RESOURCE_POOL_SUFFIX);
}
