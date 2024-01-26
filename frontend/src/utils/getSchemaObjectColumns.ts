import * as R from "ramda";
import {
  attributesKindForDetailsViewExclude,
  attributesKindForListView,
  peersKindForForm,
  relationshipsForDetailsView,
  relationshipsForListView,
  relationshipsForTabs,
} from "../config/constants";
import { iGenericSchema, iNodeSchema } from "../state/atoms/schema.atom";
import { sortByOrderWeight } from "./common";

export const getObjectAttributes = (
  schema: iNodeSchema | iGenericSchema,
  forListView?: boolean
) => {
  if (!schema) {
    return [];
  }

  const attributes = (schema.attributes || [])
    .filter((attribute) =>
      forListView
        ? attributesKindForListView.includes(attribute.kind)
        : !attributesKindForDetailsViewExclude.includes(attribute.kind)
    )
    .map((attribute) => ({
      isAttribute: true,
      ...attribute,
    }));

  return attributes;
};

export const getObjectRelationships = (
  schema?: iNodeSchema | iGenericSchema,
  forListView?: boolean
) => {
  if (!schema) {
    return [];
  }

  const kinds = forListView ? relationshipsForListView : relationshipsForDetailsView;

  const relationships = (schema.relationships || [])
    .filter((relationship) => kinds[relationship.cardinality].includes(relationship.kind ?? ""))
    .map((relationship) => ({
      isRelationship: true,
      paginated: relationship.cardinality === "many",
      ...relationship,
    }));

  return relationships;
};

export const getTabs = (schema: iNodeSchema | iGenericSchema) => {
  if (!schema) {
    return [];
  }

  // Relationship kind to show in LIST VIEW - Attribute, Parent
  const relationships = (schema.relationships || [])
    .filter((relationship) =>
      relationshipsForTabs[relationship.cardinality].includes(relationship.kind)
    )
    .map((relationship) => ({
      label: relationship.label,
      name: relationship.name,
    }));

  return relationships;
};

// Get attributes and relationships from a schema, optional limit to trim the array
export const getSchemaObjectColumns = (
  schema?: iNodeSchema | iGenericSchema,
  fromListView?: boolean,
  limit?: number
) => {
  if (!schema) {
    return [];
  }

  const attributes = getObjectAttributes(schema, fromListView);
  const relationships = getObjectRelationships(schema, fromListView);

  const columns = sortByOrderWeight(R.concat(attributes, relationships));

  if (limit) {
    return columns.slice(0, limit);
  }

  return columns;
};

export const getGroupColumns = (schema?: iNodeSchema | iGenericSchema) => {
  if (!schema) {
    return [];
  }

  const defaultColumns = [{ label: "Type", name: "__typename" }];

  const columns = getSchemaObjectColumns(schema);

  return [...defaultColumns, ...columns];
};

export const getAttributeColumnsFromNodeOrGenericSchema = (
  schema: iNodeSchema | undefined,
  generic: iGenericSchema | undefined
) => {
  if (generic) {
    return getSchemaObjectColumns(generic);
  }

  if (schema) {
    return getSchemaObjectColumns(schema);
  }

  return [];
};

export const getObjectTabs = (tabs: any[], data: any) => {
  return tabs.map((tab: any) => ({
    ...tab,
    count: data[tab.name].count,
  }));
};

// Used by the form to display the fields
export const getObjectRelationshipsForForm = (schema?: iNodeSchema | iGenericSchema) => {
  const relationships = (schema?.relationships || [])
    .filter(
      (relationship) =>
        peersKindForForm.includes(relationship?.kind ?? "") || relationship.cardinality === "one"
    )
    .filter(Boolean);

  return relationships;
};

// Used by the query to retrieve the data for the form
export const getObjectPeers = (schema?: iNodeSchema | iGenericSchema) => {
  const peers = getObjectRelationshipsForForm(schema)
    .map((relationship) => relationship.peer)
    .filter(Boolean);

  return peers;
};
