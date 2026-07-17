import { useAtomValue } from "jotai";

import { sortByOrderWeight } from "@/shared/utils/common";

import { isSortableAttribute } from "@/entities/nodes/sort/domain/rules/is-sortable-attribute";
import { isSortableRelationship } from "@/entities/nodes/sort/domain/rules/is-sortable-relationship";
import {
  buildAttributeSortField,
  buildRelationshipSortField,
} from "@/entities/nodes/sort/domain/rules/sort-field";
import {
  NODE_METADATA_SORT_OPTIONS,
  type SortableField,
} from "@/entities/nodes/sort/ui/sort-options";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { resolveSchema } from "@/entities/schema/domain/rules/resolve-schema";
import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
  templateSchemasAtom,
} from "@/entities/schema/stores/schema.atom";

// "Peer › Attribute" separator. En-spaces (U+2002) around the chevron keep it from looking cramped.
const PEER_LABEL_SEPARATOR = " › ";

/**
 * Flat list of every field a node can be sorted by: its own attributes,
 * attributes reached through cardinality-one relationships, and node metadata.
 */
export function useSortableFields(schema: ModelSchema): SortableField[] {
  const nodeSchemas = useAtomValue(nodeSchemasAtom);
  const genericSchemas = useAtomValue(genericSchemasAtom);
  const profileSchemas = useAtomValue(profileSchemasAtom);
  const templateSchemas = useAtomValue(templateSchemasAtom);

  const attributeFields: SortableField[] = sortByOrderWeight(schema.attributes ?? [])
    .filter(isSortableAttribute)
    .map((attribute) => ({
      field: buildAttributeSortField(attribute.name),
      label: attribute.label ?? attribute.name,
      fieldSchema: attribute,
    }));

  const relationshipFields: SortableField[] = sortByOrderWeight(schema.relationships ?? [])
    .filter(isSortableRelationship)
    .flatMap((relationship) => {
      const { schema: peerSchema } = resolveSchema(relationship.peer, {
        nodeSchemas,
        genericSchemas,
        profileSchemas,
        templateSchemas,
      });
      if (!peerSchema) return [];

      const relationshipLabel = relationship.label ?? relationship.name;
      const peerAttributes = (peerSchema.attributes ?? []).filter(isSortableAttribute);

      return sortByOrderWeight(peerAttributes).map((attribute) => {
        const attributeField = buildAttributeSortField(attribute.name);
        const attributeLabel = attribute.label ?? attribute.name;

        return {
          field: buildRelationshipSortField(relationship.name, attributeField),
          label: `${relationshipLabel}${PEER_LABEL_SEPARATOR}${attributeLabel}`,
          fieldSchema: relationship,
        };
      });
    });

  return [...attributeFields, ...relationshipFields, ...NODE_METADATA_SORT_OPTIONS];
}
