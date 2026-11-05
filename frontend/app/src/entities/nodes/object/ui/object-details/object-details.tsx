import { DetailsLayout } from "@/shared/components/layout/details-layout";
import { useTitle } from "@/shared/hooks/useTitle";
import { sortByOrderWeight } from "@/shared/utils/common";

import type {
  NodeFileObject,
  NodeObjectWithMetadata,
} from "@/entities/nodes/object/domain/model/node";
import { FILE_OBJECT_KIND } from "@/entities/nodes/object/domain/model/object-kinds";
import { getAttributesVisibleInDetailedView } from "@/entities/nodes/object/domain/rules/get-attributes-visible-in-detailed-view";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { groupFieldsBySection } from "@/entities/nodes/object/domain/rules/group-fields-by-section";
import { isFromResourcePoolRelationship } from "@/entities/nodes/object/domain/rules/is-from-resource-pool-relationship";
import { FilePreviewCard } from "@/entities/nodes/object/ui/object-details/file-preview-card";
import { ObjectActivitiesCard } from "@/entities/nodes/object/ui/object-details/object-activities-card";
import { getRelationshipsVisibleInDataDisplay } from "@/entities/nodes/object/ui/object-details/object-data-display/object-data-display";
import { ObjectDetailsCard } from "@/entities/nodes/object/ui/object-details/object-details-card";
import { ObjectProfilesGroupsCard } from "@/entities/nodes/object/ui/object-details/object-profiles-groups-card";
import type { Permission } from "@/entities/permission/domain/model/permission";
import { GENERIC_REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";
import { RepositoryObjectDetails } from "@/entities/repository/ui/repository-object-details";
import type { AttributeSchema, ModelSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";
import { isRelationshipSchema } from "@/entities/schema/domain/rules/is-relationship-schema";

interface ObjectDetailsProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
}

export function ObjectDetails({ objectSchema, objectData, permission }: ObjectDetailsProps) {
  useTitle(`${getNodeLabel(objectData)} details`);

  return (
    <DetailsLayout>
      <DetailsLayout.Main>
        {isOfKind(GENERIC_REPOSITORY_KIND, objectSchema) ? (
          <RepositoryObjectDetails
            objectSchema={objectSchema}
            objectData={objectData}
            permission={permission}
          />
        ) : (
          <ObjectDetailsSections
            objectSchema={objectSchema}
            objectData={objectData}
            permission={permission}
          />
        )}

        {isOfKind(FILE_OBJECT_KIND, objectSchema) && (
          <FilePreviewCard objectData={objectData as unknown as NodeFileObject} />
        )}
      </DetailsLayout.Main>

      <DetailsLayout.Aside>
        <ObjectProfilesGroupsCard
          objectSchema={objectSchema}
          objectData={objectData}
          permission={permission}
        />
        <ObjectActivitiesCard objectKind={objectData.__typename} objectId={objectData.id} />
      </DetailsLayout.Aside>
    </DetailsLayout>
  );
}

function ObjectDetailsSections({ objectSchema, objectData, permission }: ObjectDetailsProps) {
  const allRelationships = objectSchema.relationships ?? [];
  const fields = sortByOrderWeight([
    ...getAttributesVisibleInDetailedView(objectSchema.attributes ?? []),
    ...getRelationshipsVisibleInDataDisplay(allRelationships),
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
