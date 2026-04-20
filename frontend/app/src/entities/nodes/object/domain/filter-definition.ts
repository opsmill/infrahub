import { warnUnexpectedType } from "@/shared/utils/common";

import type { DecisionOption } from "@/entities/role-manager/domain/get-decision-options";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

export type AttributeFilterDefinition = {
  type: "attribute";
  schema: AttributeSchema;
};

export type RelationshipFilterDefinition = {
  type: "relationship";
  schema: RelationshipSchema;
};

export type MetadataDateFilterDefinition = {
  type: "metadata-date";
  name: string;
  label: string;
};

export type MetadataUserFilterDefinition = {
  type: "metadata-user";
  name: string;
  label: string;
  peer: string;
};

export type PermissionDecisionFilterDefinition = {
  type: "permission-decision";
  schema: AttributeSchema;
  options: DecisionOption[];
};

export type FilterDefinition =
  | AttributeFilterDefinition
  | RelationshipFilterDefinition
  | PermissionDecisionFilterDefinition
  | MetadataDateFilterDefinition
  | MetadataUserFilterDefinition;

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
