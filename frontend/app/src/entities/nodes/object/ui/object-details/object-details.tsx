import type React from "react";

import { Col } from "@/shared/components/container";
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
  /**
   * Optional extra content rendered inside the LEFT column, directly below the
   * object-details card (and the file-preview card), so it shares the same column
   * width, gap, and the grid's padding. Defaults to nothing, so every other caller
   * is unaffected. Used by the profile tab to slot in the user-preferences card.
   */
  leftColumnExtra?: React.ReactNode;
}

export function ObjectDetails({
  objectSchema,
  objectData,
  permission,
  leftColumnExtra,
}: ObjectDetailsProps) {
  useTitle(`${getNodeLabel(objectData)} details`);

  return (
    <div className="flex flex-col gap-2 overflow-auto p-2 xl:grid xl:grid-cols-3 xl:items-start">
      <Col className="shrink-0 grow md:col-span-2">
        <ObjectDetailsCard
          objectSchema={objectSchema}
          objectData={objectData}
          permission={permission}
        />

        {isOfKind(FILE_OBJECT_KIND, objectSchema) && (
          <FilePreviewCard objectData={objectData as unknown as NodeFileObject} />
        )}

        {leftColumnExtra}
      </Col>

      <Col>
        <ObjectProfilesGroupsCard
          objectSchema={objectSchema}
          objectData={objectData}
          permission={permission}
        />
        <ObjectActivitiesCard objectKind={objectData.__typename} objectId={objectData.id} />
      </Col>
    </div>
  );
}
