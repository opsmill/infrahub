import { DetailsLayout } from "@/shared/components/layout/details-layout";
import { useTitle } from "@/shared/hooks/useTitle";

import type {
  NodeFileObject,
  NodeObjectWithMetadata,
} from "@/entities/nodes/object/domain/model/node";
import { FILE_OBJECT_KIND } from "@/entities/nodes/object/domain/model/object-kinds";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { FilePreviewCard } from "@/entities/nodes/object/ui/object-details/file-preview-card";
import { ObjectActivitiesCard } from "@/entities/nodes/object/ui/object-details/object-activities-card";
import { ObjectDetailsCard } from "@/entities/nodes/object/ui/object-details/object-details-card";
import { ObjectProfilesGroupsCard } from "@/entities/nodes/object/ui/object-details/object-profiles-groups-card";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";

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
        <ObjectDetailsCard
          objectSchema={objectSchema}
          objectData={objectData}
          permission={permission}
        />

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
