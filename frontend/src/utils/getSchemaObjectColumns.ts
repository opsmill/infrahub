import { isValid, parseISO } from "date-fns";
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
  schema: iNodeSchema | iGenericSchema | undefined,
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
    .filter(
      (relationship) =>
        relationship.cardinality &&
        kinds[relationship.cardinality].includes(relationship.kind ?? "")
    )
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
    .filter(
      (relationship) =>
        relationship.cardinality &&
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
    count: data[tab.name]?.count,
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

export const getFieldValue = (row: any, attribute: any) => {
  const value = row?.[attribute.name] ? row[attribute.name].value : attribute.default_value;

  if (attribute.kind === "DateTime") {
    if (isValid(value)) {
      return value;
    }

    if (isValid(parseISO(value))) {
      return parseISO(value);
    }

    return null;
  }

  return value ?? null;
};

export const getRelationshipValue = (row: any, field: any) => {
  if (!row || !row[field.name]) {
    return "";
  }

  const value = row[field.name].node ?? row[field.name];

  if (!value) {
    return "";
  }

  if (value.id) {
    return value.id;
  }

  if (value.edges) {
    return value.edges.map((edge: any) => edge.node.id);
  }

  return "";
};

// Inlcude current value in the options to make it available in the select component
export const getRelationshipOptions = (row: any, field: any, schemas: any[], generics: any[]) => {
  const value = row && (row[field.name]?.node ?? row[field.name]);

  if (!value) {
    return [];
  }

  if (value.edges) {
    return value.edges.map((edge: any) => ({
      name: edge.node.display_label,
      id: edge.node.id,
    }));
  }

  const generic = generics.find((generic: any) => generic.kind === field.peer);

  if (generic) {
    const options = (generic.used_by || []).map((name: string) => {
      const relatedSchema = schemas.find((s: any) => s.kind === name);

      if (relatedSchema) {
        return {
          id: name,
          name: relatedSchema.name,
        };
      }
    });

    return options;
  }

  const option = {
    name: value.display_label,
    id: value.id,
  };

  // Initial option for relationships to make the current value available
  return [option];
};

export const getOptionsFromAttribute = (attribute: any, value: any) => {
  if (attribute.kind === "List") {
    return value?.map((option: any) => ({
      name: option,
      id: option,
    }));
  }

  if (attribute.enum) {
    return attribute.enum?.map((option: any) => ({
      name: option,
      id: option,
    }));
  }

  if (attribute.choices) {
    return attribute.choices?.map((option: any) => ({
      ...option,
      name: option.label,
      id: option.name,
    }));
  }

  return [];
};

export const getOptionsFromRelationship = (options: any[] = [], schemas?: any, generic?: any) => {
  if (!generic) {
    return options.map((option: any) => ({
      name: option.display_label,
      id: option.id,
    }));
  }

  if (generic) {
    return (generic.used_by || []).map((name: string) => {
      const relatedSchema = schemas.find((s: any) => s.kind === name);

      if (relatedSchema) {
        return {
          name: relatedSchema.name,
          id: name,
        };
      }
    });
  }

  return [];
};
