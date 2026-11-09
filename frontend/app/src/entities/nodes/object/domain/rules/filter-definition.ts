import { warnUnexpectedType } from "@/shared/utils/common";

import type { FilterDefinition } from "@/entities/nodes/object/domain/model/filter-definition";

export function getFilterDefinitionName(def: FilterDefinition): string {
  switch (def.type) {
    case "attribute":
    case "relationship":
    case "permission-decision":
      return def.schema.name;
    case "metadata-date":
    case "metadata-user":
      return def.name;
    default:
      warnUnexpectedType(def);
      return "???";
  }
}

export function getFilterDefinitionLabel(def: FilterDefinition): string {
  switch (def.type) {
    case "attribute":
    case "relationship":
    case "permission-decision":
      return def.schema.label ?? def.schema.name;
    case "metadata-date":
    case "metadata-user":
      return def.label;
    default:
      warnUnexpectedType(def);
      return "???";
  }
}
