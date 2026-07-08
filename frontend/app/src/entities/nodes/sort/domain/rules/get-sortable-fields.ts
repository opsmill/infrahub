import { sortByOrderWeight } from "@/shared/utils/common";

import type { SortableField } from "@/entities/nodes/sort/domain/model/sort";
import {
  getSortableAttributes,
  isSortableAttribute,
} from "@/entities/nodes/sort/domain/rules/get-sortable-attributes";
import type { ModelSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";
import { getSchema } from "@/entities/schema/domain/use-cases/get-schema";

// "Peer › Attribute" separator. En-spaces ( ) around the chevron keep it from looking cramped.
const PEER_LABEL_SEPARATOR = " › ";

function getSortableFieldsOfRelationship(
  relationship: RelationshipSchema,
  peerSchema: ModelSchema
): SortableField[] {
  const sortablePeerAttributes = (peerSchema.attributes ?? []).filter(isSortableAttribute);
  const orderedPeerAttributes = sortByOrderWeight(sortablePeerAttributes);

  const relationshipLabel = relationship.label ?? relationship.name;

  return orderedPeerAttributes.map((attribute) => {
    const attributeLabel = attribute.label ?? attribute.name;
    return {
      field: `${relationship.name}__${attribute.name}__value`,
      label: `${relationshipLabel}${PEER_LABEL_SEPARATOR}${attributeLabel}`,
    };
  });
}

const NODE_METADATA_SORTABLE_FIELDS: SortableField[] = [
  { field: "node_metadata__created_at", label: "Created at" },
  { field: "node_metadata__updated_at", label: "Updated at" },
];

export function getSortableFields(schema: ModelSchema): SortableField[] {
  const attributeFields = getSortableAttributes(schema.attributes ?? []);

  const relationshipFields = (schema.relationships ?? [])
    .filter((relationship) => relationship.cardinality === "one")
    .flatMap((relationship) => {
      const peerSchema = getSchema(relationship.peer).schema;
      if (!peerSchema) return [];

      return getSortableFieldsOfRelationship(relationship, peerSchema);
    });

  return [...attributeFields, ...relationshipFields, ...NODE_METADATA_SORTABLE_FIELDS];
}
