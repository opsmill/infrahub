import type { DecisionOption } from "@/entities/role-manager/domain/use-cases/get-decision-options";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";

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
