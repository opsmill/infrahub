import { sortByOrderWeight } from "@/shared/utils/common";

import type { NodeObjectWithMetadata } from "@/entities/nodes/object/domain/model/node";
import { getAttributesVisibleInDetailedView } from "@/entities/nodes/object/domain/rules/get-attributes-visible-in-detailed-view";
import { groupFieldsBySection } from "@/entities/nodes/object/domain/rules/group-fields-by-section";
import { isFromResourcePoolRelationship } from "@/entities/nodes/object/domain/rules/is-from-resource-pool-relationship";
import { getRelationshipsVisibleInDataDisplay } from "@/entities/nodes/object/ui/object-details/object-data-display/object-data-display";
import { ObjectDetailsCard } from "@/entities/nodes/object/ui/object-details/object-details-card";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { AttributeSchema, ModelSchema } from "@/entities/schema/domain/model/schema";
import { isRelationshipSchema } from "@/entities/schema/domain/rules/is-relationship-schema";

interface ObjectDetailsSectionsProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
  excludeRelationships?: string[];
}

export function ObjectDetailsSections({
  objectSchema,
  objectData,
  permission,
  excludeRelationships,
}: ObjectDetailsSectionsProps) {
  const allRelationships = objectSchema.relationships ?? [];
  const fields = sortByOrderWeight([
    ...getAttributesVisibleInDetailedView(objectSchema.attributes ?? []),
    ...getRelationshipsVisibleInDataDisplay(allRelationships, excludeRelationships),
  ]);
  // The visibility filter drops pool relationships, but the data display needs them to render pool rows.
  const poolRelationships = allRelationships.filter((relationship) =>
    isFromResourcePoolRelationship(relationship.name)
  );
  const sections = groupFieldsBySection(
    objectSchema.containers,
    fields,
    (field) => field.container
  );

  if (sections.length === 0) {
    return (
      <ObjectDetailsCard
        objectSchema={objectSchema}
        objectData={objectData}
        permission={permission}
        excludeRelationships={excludeRelationships}
      />
    );
  }

  return sections.map(({ key, kind, container, items }) => {
    const attributes = items.filter((item): item is AttributeSchema => !isRelationshipSchema(item));
    const relationships = [...items.filter(isRelationshipSchema), ...poolRelationships];
    const isDetails = kind === "details";

    return (
      <ObjectDetailsCard
        key={key}
        title={container.label}
        description={isDetails ? undefined : container.description}
        defaultCollapsed={isDetails ? undefined : container.collapsed}
        objectSchema={{ ...objectSchema, attributes, relationships }}
        objectData={objectData}
        permission={permission}
      />
    );
  });
}
