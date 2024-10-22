import { SelectOption } from "@/components/inputs/select";
import {
  attributesKindForDetailsViewExclude,
  attributesKindForListView,
  relationshipsForDetailsView,
  relationshipsForListView,
  relationshipsForTabs,
} from "@/config/constants";
import { store } from "@/state";
import { iGenericSchema, iNodeSchema, profilesAtom } from "@/state/atoms/schema.atom";
import * as R from "ramda";
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

export const getTabs = (schema?: iNodeSchema | iGenericSchema) => {
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

export const getObjectTabs = (tabs: any[], data: any) => {
  return tabs.map((tab: any) => ({
    ...tab,
    count: data[tab.name]?.count,
  }));
};

// Include current value in the options to make it available in the select component
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
      const profiles = store.get(profilesAtom);

      const relatedSchema = [...schemas, ...profiles].find((s: any) => s.kind === name);

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

export const getOptionsFromAttribute = (attribute: any, value: any): Array<SelectOption> => {
  if (attribute.kind === "List") {
    return (value || [])?.map((option: any) => ({
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
  peerField?: string;
};

export const getOptionsFromRelationship = ({
  options,
  schemas,
  generic,
  peerField,
}: tgetOptionsFromRelationship) => {
  if (!generic) {
    return options.map((option: any) => ({
      name: peerField ? (option[peerField]?.value ?? option[peerField]) : option.display_label,
      id: option.id,
      kind: option.__typename,
    }));
  }

  if (generic) {
    return (generic.used_by || []).map((name: string) => {
      const relatedSchema = schemas.find((s: any) => s.kind === name);

      if (relatedSchema) {
        return {
          name: relatedSchema.name,
          id: name,
          kind: relatedSchema.kind,
        };
      }
    });
  }

  return [];
};
