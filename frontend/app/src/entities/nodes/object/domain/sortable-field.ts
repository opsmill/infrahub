import { sortByOrderWeight } from "@/shared/utils/common";

import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import { getSchema } from "@/entities/schema/domain/get-schema";
import type { AttributeKind, AttributeSchema, ModelSchema } from "@/entities/schema/types";

/** An `order_by` field key, e.g. `name__value`, `tags__name__value`, `node_metadata__created_at`. */
export type SortFieldKey = `${string}__${string}`;
export type SortDirection = "ASC" | "DESC";

export interface SortableField {
  field: SortFieldKey;
  label: string;
}

const SORTABLE_ATTRIBUTE_KINDS = new Set<AttributeKind>([
  ATTRIBUTE_KIND.TEXT,
  ATTRIBUTE_KIND.TEXTAREA,
  ATTRIBUTE_KIND.EMAIL,
  ATTRIBUTE_KIND.URL,
  ATTRIBUTE_KIND.DATETIME,
  ATTRIBUTE_KIND.NUMBER,
  ATTRIBUTE_KIND.BANDWIDTH,
  ATTRIBUTE_KIND.DROPDOWN,
  ATTRIBUTE_KIND.COLOR,
  ATTRIBUTE_KIND.CHECKBOX,
  ATTRIBUTE_KIND.BOOLEAN,
  ATTRIBUTE_KIND.MAC_ADDRESS,
  ATTRIBUTE_KIND.IP_HOST,
  ATTRIBUTE_KIND.IP_NETWORK,
  ATTRIBUTE_KIND.ID,
]);

const NODE_METADATA_SORTABLE_FIELDS: SortableField[] = [
  { field: "node_metadata__created_at", label: "Created at" },
  { field: "node_metadata__updated_at", label: "Updated at" },
];

// "Peer › Attribute" separator. En-spaces ( ) around the chevron keep it from looking cramped.
const PEER_LABEL_SEPARATOR = " › ";

const attributeLabel = (attribute: AttributeSchema) => attribute.label ?? attribute.name;

function isSortableAttribute(attribute: AttributeSchema): boolean {
  return SORTABLE_ATTRIBUTE_KINDS.has(attribute.kind as AttributeKind);
}

function getAttributeSortableFields(schema: ModelSchema): SortableField[] {
  const sortableAttributes = (schema.attributes ?? []).filter(isSortableAttribute);

  return sortByOrderWeight(sortableAttributes).map((attribute) => ({
    field: `${attribute.name}__value`,
    label: attributeLabel(attribute),
  }));
}

function getRelationshipSortableFields(schema: ModelSchema): SortableField[] {
  const cardinalityOneRelationships = (schema.relationships ?? []).filter(
    (relationship) => relationship.cardinality === "one"
  );

  return sortByOrderWeight(cardinalityOneRelationships).flatMap((relationship) => {
    const peerSchema = getSchema(relationship.peer).schema;
    if (!peerSchema) return [];

    const relationshipLabel = relationship.label ?? relationship.name;
    const sortablePeerAttributes = (peerSchema.attributes ?? []).filter(isSortableAttribute);

    return sortByOrderWeight(sortablePeerAttributes).map((attribute) => ({
      field: `${relationship.name}__${attribute.name}__value`,
      label: `${relationshipLabel}${PEER_LABEL_SEPARATOR}${attributeLabel(attribute)}`,
    }));
  });
}

export function getSortableFields(schema: ModelSchema): SortableField[] {
  return [
    ...getAttributeSortableFields(schema),
    ...getRelationshipSortableFields(schema),
    ...NODE_METADATA_SORTABLE_FIELDS,
  ];
}
