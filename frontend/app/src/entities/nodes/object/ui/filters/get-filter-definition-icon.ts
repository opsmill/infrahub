import { warnUnexpectedType } from "@/shared/utils/common";

import type { FilterDefinition } from "@/entities/nodes/object/domain/filter-definition";
import type { AttributeKind } from "@/entities/schema/types";
import { ATTRIBUTE_ICONS } from "@/entities/schema/ui/field-schema-icon";

export function getFilterDefinitionIcon(def: FilterDefinition): string {
  switch (def.type) {
    case "attribute":
    case "permission-decision":
      return ATTRIBUTE_ICONS[def.schema.kind as AttributeKind] ?? "mdi:filter-variant";
    case "relationship":
      return "mdi:cube-outline";
    case "metadata-date":
      return "mdi:calendar-clock";
    case "metadata-user":
      return "mdi:account";
    default:
      warnUnexpectedType(def);
      return "mdi:filter-variant";
  }
}
