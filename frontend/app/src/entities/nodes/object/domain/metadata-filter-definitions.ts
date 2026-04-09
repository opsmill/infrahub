import type {
  FilterDefinition,
  MetadataDateFilterDefinition,
  MetadataUserFilterDefinition,
} from "@/entities/nodes/object/domain/filter-definition";

export const METADATA_CREATED_AT: MetadataDateFilterDefinition = {
  type: "metadata-date",
  name: "node_metadata__created_at",
  label: "Created at",
};

export const METADATA_UPDATED_AT: MetadataDateFilterDefinition = {
  type: "metadata-date",
  name: "node_metadata__updated_at",
  label: "Updated at",
};

export const METADATA_CREATED_BY: MetadataUserFilterDefinition = {
  type: "metadata-user",
  name: "node_metadata__created_by",
  label: "Created by",
  peer: "CoreAccount",
};

export const METADATA_UPDATED_BY: MetadataUserFilterDefinition = {
  type: "metadata-user",
  name: "node_metadata__updated_by",
  label: "Updated by",
  peer: "CoreAccount",
};

export const ALL_METADATA_FILTERS: FilterDefinition[] = [
  METADATA_CREATED_AT,
  METADATA_UPDATED_AT,
  METADATA_CREATED_BY,
  METADATA_UPDATED_BY,
];
