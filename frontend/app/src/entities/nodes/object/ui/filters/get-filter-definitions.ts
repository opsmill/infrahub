import {
  ACCOUNT_GROUP_OBJECT,
  ACCOUNT_OBJECT,
  ACCOUNT_ROLE_OBJECT,
  GLOBAL_PERMISSION_OBJECT,
  OBJECT_PERMISSION_OBJECT,
} from "@/shared/config/constants";
import { sortByOrderWeight } from "@/shared/utils/common";

import type { FilterDefinition } from "@/entities/nodes/object/domain/filter-definition";
import { ALL_METADATA_FILTERS } from "@/entities/nodes/object/domain/metadata-filter-definitions";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list-view";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list-view";
import { isFromResourcePoolRelationship } from "@/entities/nodes/object/utils/is-from-resource-pool-relationship";
import { getDecisionOptions } from "@/entities/role-manager/domain/get-decision-options";
import {
  ACCOUNT_TABLE_ATTRIBUTES,
  ACCOUNT_TABLE_RELATIONSHIPS,
} from "@/entities/role-manager/ui/get-account-table-columns";
import {
  GLOBAL_PERMISSIONS_TABLE_ATTRIBUTES,
  GLOBAL_PERMISSIONS_TABLE_RELATIONSHIPS,
} from "@/entities/role-manager/ui/get-global-permissions-table-columns";
import {
  GROUP_TABLE_ATTRIBUTES,
  GROUP_TABLE_RELATIONSHIPS,
} from "@/entities/role-manager/ui/get-group-table-columns";
import {
  OBJECT_PERMISSION_TABLE_ATTRIBUTES,
  OBJECT_PERMISSION_TABLE_RELATIONSHIPS,
} from "@/entities/role-manager/ui/get-object-permission-table-columns";
import {
  ROLE_TABLE_ATTRIBUTES,
  ROLE_TABLE_RELATIONSHIPS,
} from "@/entities/role-manager/ui/get-role-table-columns";
import type { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

function mapFieldToDefinition(
  schemaKind: ModelSchema["kind"],
  field: AttributeSchema | RelationshipSchema
): FilterDefinition {
  if ("peer" in field) {
    return { type: "relationship", schema: field };
  }

  const decisionOptions = getDecisionOptions(schemaKind, field.name);

  return decisionOptions
    ? { type: "permission-decision", schema: field, options: decisionOptions }
    : { type: "attribute", schema: field };
}

function getOrderedFieldDefinitions(
  schemaKind: ModelSchema["kind"],
  fields: Array<AttributeSchema | RelationshipSchema>
): FilterDefinition[] {
  return sortByOrderWeight(fields).map((field) => mapFieldToDefinition(schemaKind, field));
}

function getDefaultObjectFieldDefinitions(schema: ModelSchema): FilterDefinition[] {
  const attributes = getAttributesVisibleInListView(schema.attributes ?? []);
  const relationships = getRelationshipsVisibleInListView(schema.relationships ?? []).filter(
    (relationship) => !isFromResourcePoolRelationship(relationship.name)
  );

  return getOrderedFieldDefinitions(schema.kind, [...attributes, ...relationships]);
}

function getDefinitionsFromFieldNames(
  schema: ModelSchema,
  {
    attributesVisible,
    relationshipsVisible,
  }: {
    attributesVisible: string[];
    relationshipsVisible: string[];
  }
): FilterDefinition[] {
  const attributeNames = new Set(attributesVisible);
  const relationshipNames = new Set(relationshipsVisible);

  return getOrderedFieldDefinitions(schema.kind, [
    ...(schema.attributes ?? []).filter(({ name }) => attributeNames.has(name)),
    ...(schema.relationships ?? []).filter(({ name }) => relationshipNames.has(name)),
  ]);
}

function getFilterDefinitionsFromSchemaFields(schema: ModelSchema): FilterDefinition[] {
  if (isOfKind(OBJECT_PERMISSION_OBJECT, schema)) {
    return getDefinitionsFromFieldNames(schema, {
      attributesVisible: OBJECT_PERMISSION_TABLE_ATTRIBUTES,
      relationshipsVisible: OBJECT_PERMISSION_TABLE_RELATIONSHIPS,
    });
  }

  if (isOfKind(GLOBAL_PERMISSION_OBJECT, schema)) {
    return getDefinitionsFromFieldNames(schema, {
      attributesVisible: GLOBAL_PERMISSIONS_TABLE_ATTRIBUTES,
      relationshipsVisible: GLOBAL_PERMISSIONS_TABLE_RELATIONSHIPS,
    });
  }

  if (isOfKind(ACCOUNT_ROLE_OBJECT, schema)) {
    return getDefinitionsFromFieldNames(schema, {
      attributesVisible: ROLE_TABLE_ATTRIBUTES,
      relationshipsVisible: ROLE_TABLE_RELATIONSHIPS,
    });
  }

  if (isOfKind(ACCOUNT_OBJECT, schema)) {
    return getDefinitionsFromFieldNames(schema, {
      attributesVisible: ACCOUNT_TABLE_ATTRIBUTES,
      relationshipsVisible: ACCOUNT_TABLE_RELATIONSHIPS,
    });
  }

  if (isOfKind(ACCOUNT_GROUP_OBJECT, schema)) {
    return getDefinitionsFromFieldNames(schema, {
      attributesVisible: GROUP_TABLE_ATTRIBUTES,
      relationshipsVisible: GROUP_TABLE_RELATIONSHIPS,
    });
  }

  return getDefaultObjectFieldDefinitions(schema);
}

export function getFilterDefinitions(schema: ModelSchema): FilterDefinition[] {
  return [...getFilterDefinitionsFromSchemaFields(schema), ...ALL_METADATA_FILTERS];
}
