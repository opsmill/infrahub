import type { AttributeKind, AttributeSchema, RelationshipSchema } from "@/entities/schema/types";
import { ATTRIBUTE_ICONS } from "@/entities/schema/ui/field-schema-icon";

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

export type FilterDefinition =
  | AttributeFilterDefinition
  | RelationshipFilterDefinition
  | MetadataDateFilterDefinition
  | MetadataUserFilterDefinition;

export function getFilterDefinitionName(def: FilterDefinition): string {
  switch (def.type) {
    case "attribute":
    case "relationship":
      return def.schema.name;
    case "metadata-date":
    case "metadata-user":
      return def.name;
  }
}

export function getFilterDefinitionLabel(def: FilterDefinition): string {
  switch (def.type) {
    case "attribute":
    case "relationship":
      return def.schema.label ?? def.schema.name;
    case "metadata-date":
    case "metadata-user":
      return def.label;
  }
}

export function getFilterDefinitionIcon(def: FilterDefinition): string {
  switch (def.type) {
    case "attribute":
      return ATTRIBUTE_ICONS[def.schema.kind as AttributeKind] ?? "mdi:filter-variant";
    case "relationship":
      return "mdi:cube-outline";
    case "metadata-date":
      return "mdi:calendar-clock";
    case "metadata-user":
      return "mdi:account";
  }
}
