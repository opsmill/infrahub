import {
  attributesKindForDetailsViewExclude,
  relationshipKindForForm,
  relationshipsForDetailsView,
  relationshipsForListView,
} from "@/shared/config/constants";
import { sortByOrderWeight } from "@/shared/utils/common";

import type { RelationshipKind } from "@/entities/nodes/types";
import { ATTRIBUTE_KINDS_FOR_LIST_VIEW } from "@/entities/schema/constants";
import type { AttributeKind, ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";

type tgetObjectAttributes = {
  schema: ModelSchema | undefined;
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
        ? ATTRIBUTE_KINDS_FOR_LIST_VIEW.includes(attribute.kind as AttributeKind)
        : !attributesKindForDetailsViewExclude.includes(attribute.kind)
    )
    .map((attribute) => ({
      isAttribute: true,
      ...attribute,
    }));

  return attributes;
};

type tgetObjectRelationships = {
  schema?: ModelSchema;
  forListView?: boolean;
  forQuery?: boolean;
  forProfiles?: boolean;
};

export const getObjectRelationships = ({
  schema,
  forListView,
  forQuery,
  forProfiles,
}: tgetObjectRelationships) => {
  if (!schema) {
    return [];
  }

  const kinds = forListView ? relationshipsForListView : relationshipsForDetailsView;

  const relationships = (schema.relationships || [])
    .filter((relationship) => {
      if (forProfiles) {
        // For profiles, include optional relationships that are form-eligible
        return (
          relationship.optional &&
          relationshipKindForForm.includes(relationship.kind as RelationshipKind)
        );
      }
      return (
        (forQuery ? relationship.read_only : true) &&
        relationship.cardinality &&
        kinds[relationship.cardinality].includes(relationship.kind ?? "")
      );
    })
    .map((relationship) => ({
      isRelationship: true,
      paginated: relationship.cardinality === "many",
      ...relationship,
    }));

  return relationships;
};

type tgetSchemaObjectColumns = {
  schema?: ModelSchema;
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
  const relationships = getObjectRelationships({ schema, forListView });

  const columns = sortByOrderWeight([...attributes, ...relationships]);

  if (limit) {
    return columns.slice(0, limit);
  }

  const kindColumn = {
    label: "Kind",
    name: "__typename",
  };

  // columns.length > 0 needed because of relationship-details-paginated.tsx
  // Relationship needs refactoring to handle this better
  return isGenericSchema(schema) && columns.length > 0 ? [kindColumn, ...columns] : columns;
};
