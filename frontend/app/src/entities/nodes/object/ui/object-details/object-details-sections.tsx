import { DETAILS_SECTION } from "@/entities/nodes/object/domain/model/field-section";
import type { NodeObjectWithMetadata } from "@/entities/nodes/object/domain/model/node";
import { groupFieldsBySection } from "@/entities/nodes/object/domain/rules/group-fields-by-section";
import { getDataDisplayFields } from "@/entities/nodes/object/ui/object-details/object-data-display/object-data-display";
import { ObjectDetailsCard } from "@/entities/nodes/object/ui/object-details/object-details-card";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

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
  const sections = groupFieldsBySection(
    objectSchema.containers,
    getDataDisplayFields({ objectSchema, excludeRelationships }),
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

  return sections.map(({ container, items }) => (
    <ObjectDetailsCard
      key={container.name}
      title={container.label}
      section={container.name === DETAILS_SECTION.name ? undefined : container}
      fieldNames={items.map((item) => item.name)}
      objectSchema={objectSchema}
      objectData={objectData}
      permission={permission}
    />
  ));
}
