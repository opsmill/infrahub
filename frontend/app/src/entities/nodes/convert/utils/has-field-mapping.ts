import type { ConvertFieldMapping } from "@/entities/nodes/convert/types";

export function hasFieldMapping(mapping: ConvertFieldMapping | undefined): boolean {
  return !!mapping?.source_field_name;
}
