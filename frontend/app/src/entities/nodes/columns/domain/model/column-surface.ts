import { sortByOrderWeight } from "@/shared/utils/common";

import { getIpAddressAttributesVisibleInListView } from "@/entities/ipam/ip-addresses/domain/rules/get-ip-address-attributes-visible-in-list-view";
import { getIpAddressRelationshipsVisibleInListView } from "@/entities/ipam/ip-addresses/domain/rules/get-ip-address-relationships-visible-in-list-view";
import { getPrefixAttributesVisibleInListView } from "@/entities/ipam/ip-prefixes/domain/rules/get-prefix-attributes-visible-in-list-view";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/domain/rules/get-attributes-visible-in-list-view";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/domain/rules/get-relationships-visible-in-list-view";
import { isFromResourcePoolRelationship } from "@/entities/nodes/object/domain/rules/is-from-resource-pool-relationship";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";

export type ColumnSurfaceId = "object" | "relationship" | "ip-address" | "ip-prefix";

type FieldSchema = AttributeSchema | RelationshipSchema;

/**
 * Describes one table surface's column rules as data, so no consumer branches on `id`.
 *
 * `getDefault*` must be the very functions that surface's column builder calls, otherwise the
 * picker can offer a column the table cannot render. `canReveal` is false wherever the fetch path
 * has no reveal seam: the candidate list then collapses to the defaults.
 */
export interface ColumnSurface {
  readonly id: ColumnSurfaceId;
  readonly fixedColumnIds: readonly string[];
  readonly getDefaultAttributes: (attributes: AttributeSchema[]) => AttributeSchema[];
  readonly getDefaultRelationships: (relationships: RelationshipSchema[]) => RelationshipSchema[];
  readonly excludeField: (field: FieldSchema) => boolean;
  readonly orderFields: (fields: FieldSchema[]) => FieldSchema[];
  readonly canReveal: boolean;
}

const FIXED_COLUMN_IDS = ["id", "objectKind", "actions"] as const;

export const OBJECT_COLUMN_SURFACE: ColumnSurface = Object.freeze({
  id: "object",
  fixedColumnIds: FIXED_COLUMN_IDS,
  getDefaultAttributes: getAttributesVisibleInListView,
  getDefaultRelationships: getRelationshipsVisibleInListView,
  // `getRelationshipsVisibleInListView` keeps `_resource_from_pool` relationships so their data is
  // fetched; only the object builder strips their columns, so only this surface excludes them.
  excludeField: (field: FieldSchema) => isFromResourcePoolRelationship(field.name),
  orderFields: sortByOrderWeight,
  canReveal: true,
});

export const RELATIONSHIP_COLUMN_SURFACE: ColumnSurface = Object.freeze({
  id: "relationship",
  fixedColumnIds: FIXED_COLUMN_IDS,
  getDefaultAttributes: getAttributesVisibleInListView,
  getDefaultRelationships: getRelationshipsVisibleInListView,
  excludeField: (field: FieldSchema) => isFromResourcePoolRelationship(field.name),
  orderFields: sortByOrderWeight,
  canReveal: false,
});

export const IP_ADDRESS_COLUMN_SURFACE: ColumnSurface = Object.freeze({
  id: "ip-address",
  fixedColumnIds: FIXED_COLUMN_IDS,
  getDefaultAttributes: getIpAddressAttributesVisibleInListView,
  getDefaultRelationships: getIpAddressRelationshipsVisibleInListView,
  // The IPAM builders render `_resource_from_pool` columns today; excluding them here would hide
  // real columns from the picker.
  excludeField: () => false,
  orderFields: (fields: FieldSchema[]) => fields,
  canReveal: false,
});

export const IP_PREFIX_COLUMN_SURFACE: ColumnSurface = Object.freeze({
  id: "ip-prefix",
  fixedColumnIds: FIXED_COLUMN_IDS,
  getDefaultAttributes: getPrefixAttributesVisibleInListView,
  getDefaultRelationships: getRelationshipsVisibleInListView,
  excludeField: () => false,
  orderFields: (fields: FieldSchema[]) => fields,
  canReveal: false,
});
