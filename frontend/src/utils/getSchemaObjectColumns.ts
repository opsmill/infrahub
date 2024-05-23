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
import { isGeneric, sortByOrderWeight } from "./common";

type tgetObjectAttributes = {
  schema: iNodeSchema | iGenericSchema | undefined;
  forListView?: boolean;
  forQuery?: boolean;
  forProfiles?: boolean;
};

export const getObjectAttributes = ({
  schema,
  forListView,
  forQuery,
  forProfiles,
}: tgetObjectAttributes) => {
  if (!schema) {
    return [];
  }

  const attributes = (schema.attributes || [])
    // Filter read_only fields in queries
    .filter((attribute) => (forQuery ? !attribute.read_only : true))
    .filter((attribute) => (forProfiles ? attribute.optional : true))
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

type tgetObjectRelationships = {
  schema?: iNodeSchema | iGenericSchema;
  forListView?: boolean;
  forQuery?: boolean;
};

export const getObjectRelationships = ({
  schema,
  forListView,
  forQuery,
}: tgetObjectRelationships) => {
  if (!schema) {
    return [];
  }

  const kinds = forListView ? relationshipsForListView : relationshipsForDetailsView;

  const relationships = (schema.relationships || [])
    .filter(
      (relationship) =>
        (forQuery ? relationship.read_only : true) &&
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

type tgetSchemaObjectColumns = {
  schema?: iNodeSchema | iGenericSchema;
  forListView?: boolean;
  forQuery?: boolean;
  limit?: number;
};

// Get attributes and relationships from a schema, optional limit to trim the array
export const getSchemaObjectColumns = ({
  schema,
  forListView,
  forQuery,
  limit,
}: tgetSchemaObjectColumns) => {
  if (!schema) {
    return [];
  }

  const attributes = getObjectAttributes({ schema, forListView, forQuery });
  const relationships = getObjectRelationships({ schema: schema, forListView });

  const columns = sortByOrderWeight(R.concat(attributes, relationships));

  if (limit) {
    return columns.slice(0, limit);
  }

  const kindColumn = {
    label: "Kind",
    name: "__typename",
  };

  // columns.length > 0 needed because of relationship-details-paginated.tsx
  // Relationship needs refactoring to handle this better
  return isGeneric(schema) && columns.length > 0 ? [kindColumn, ...columns] : columns;
};

export const getGroupColumns = (schema?: iNodeSchema | iGenericSchema) => {
  if (!schema) {
    return [];
  }

  const defaultColumns = [{ label: "Type", name: "__typename" }];

  const columns = getSchemaObjectColumns({ schema });

  return [...defaultColumns, ...columns];
};

export const getAttributeColumnsFromNodeOrGenericSchema = (
  schema: iNodeSchema | undefined,
  generic: iGenericSchema | undefined
) => {
  if (generic) {
    return getSchemaObjectColumns({ schema: generic });
  }

  if (schema) {
    return getSchemaObjectColumns({ schema });
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
export const getObjectRelationshipsForForm = (
  schema?: iNodeSchema | iGenericSchema,
  isUpdate?: boolean
) => {
  const relationships = (schema?.relationships || [])
    // Filter allowed fields
    .filter((relationship) => peersKindForForm.includes(relationship?.kind ?? ""))
    // Create form includes cardinality many but only if required, edit form doesn't include it at all
    .filter((relationship) =>
      isUpdate
        ? relationship.cardinality === "one"
        : relationship.cardinality === "one" || !relationship.optional
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

const getValue = (row: any, attribute: any, profile: any) => {
  // If the value defined was from the profile, then override it from the new profile value
  if (row && row[attribute.name]?.is_from_profile && profile) {
    return profile[attribute.name]?.value;
  }

  // What comes from the object is priority
  if (row && row[attribute.name]?.value) {
    return row[attribute.name]?.value;
  }

  if (profile && profile[attribute.name]?.value) {
    return profile[attribute.name]?.value;
  }

  return attribute.default_value;
};

type tgetFieldValue = {
  row: any;
  field: any;
  profile: any;
  isFilters?: boolean;
};

export const getFieldValue = ({ row, field, profile, isFilters }: tgetFieldValue) => {
  // No default value for filters
  if (isFilters) return "";

  const value = getValue(row, field, profile);

  if (value === null || value === undefined) return null;

  if (field.kind === "DateTime") {
    if (isValid(value)) {
      return value;
    }

    if (isValid(parseISO(value))) {
      return parseISO(value);
    }

    return null;
  }

  if (field.kind === "JSON") {
    // Ensure we use objects as values
    return typeof value === "string" ? JSON.parse(value) : value;
  }

  return value ?? null;
};

type tgetRelationshipValue = {
  row: any;
  field: any;
  isFilters?: boolean;
};

export const getRelationshipValue = ({ row, field, isFilters }: tgetRelationshipValue) => {
  // No default value for filters
  if (isFilters) return "";

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
    return {
      list: value.edges.map((edge: any) => edge.node.id),
    };
  }

  return "";
};

// Inlcude current value in the options to make it available in the select component
export const getRelationshipOptions = (row: any, field: any, schemas: any[], generics: any[]) => {
  const value = row && (row[field.name]?.node ?? row[field.name]);

  if (value?.edges) {
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

  if (!value) {
    return [];
  }

  const option = {
    name: value.display_label,
    id: value.id,
  };

  // Initial option for relationships to make the current value available
  return [option];
};

export const getSelectParent = (row: any, field: any) => {
  const parent = row[field.name]?.node?.__typename;

  return parent;
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

type tgetOptionsFromRelationship = {
  options: any[];
  schemas?: any;
  generic?: any;
};

export const getOptionsFromRelationship = ({
  options,
  schemas,
  generic,
}: tgetOptionsFromRelationship) => {
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
