import { sortByOrderWeight } from "@/shared/utils/common";

import { getIpAddressAttributesVisibleInListView } from "@/entities/ipam/ip-addresses/domain/rules/get-ip-address-attributes-visible-in-list-view";
import { getIpAddressRelationshipsVisibleInListView } from "@/entities/ipam/ip-addresses/domain/rules/get-ip-address-relationships-visible-in-list-view";
import { getPrefixAttributesVisibleInListView } from "@/entities/ipam/ip-prefixes/domain/rules/get-prefix-attributes-visible-in-list-view";
import type { ColumnSurface } from "@/entities/nodes/columns/domain/model/column-surface";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/domain/rules/get-attributes-visible-in-list-view";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/domain/rules/get-relationships-visible-in-list-view";
import { isFromResourcePoolRelationship } from "@/entities/nodes/object/domain/rules/is-from-resource-pool-relationship";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";

type FieldSchema = AttributeSchema | RelationshipSchema;

const FIXED_COLUMN_IDS = ["id", "objectKind", "actions"] as const;

export const OBJECT_COLUMN_SURFACE: ColumnSurface = {
  id: "object",
  fixedColumnIds: FIXED_COLUMN_IDS,
  getDefaultAttributes: getAttributesVisibleInListView,
  getDefaultRelationships: getRelationshipsVisibleInListView,
  // `getRelationshipsVisibleInListView` keeps `_resource_from_pool` relationships so their data is
  // fetched; only the object builder strips their columns, so only this surface excludes them.
  excludeField: (field: FieldSchema) => isFromResourcePoolRelationship(field.name),
  orderFields: sortByOrderWeight,
  canReveal: true,
};

export const RELATIONSHIP_COLUMN_SURFACE: ColumnSurface = {
  id: "relationship",
  fixedColumnIds: FIXED_COLUMN_IDS,
  getDefaultAttributes: getAttributesVisibleInListView,
  getDefaultRelationships: getRelationshipsVisibleInListView,
  excludeField: (field: FieldSchema) => isFromResourcePoolRelationship(field.name),
  orderFields: sortByOrderWeight,
  canReveal: false,
};

export const IP_ADDRESS_COLUMN_SURFACE: ColumnSurface = {
  id: "ip-address",
  fixedColumnIds: FIXED_COLUMN_IDS,
  getDefaultAttributes: getIpAddressAttributesVisibleInListView,
  getDefaultRelationships: getIpAddressRelationshipsVisibleInListView,
  // The IPAM builders render `_resource_from_pool` columns today; excluding them here would hide
  // real columns from the picker.
  excludeField: () => false,
  orderFields: (fields: FieldSchema[]) => fields,
  canReveal: false,
};

export const IP_PREFIX_COLUMN_SURFACE: ColumnSurface = {
  id: "ip-prefix",
  fixedColumnIds: FIXED_COLUMN_IDS,
  getDefaultAttributes: getPrefixAttributesVisibleInListView,
  getDefaultRelationships: getRelationshipsVisibleInListView,
  excludeField: () => false,
  orderFields: (fields: FieldSchema[]) => fields,
  canReveal: false,
};
