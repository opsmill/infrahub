import { useQueryState } from "nuqs";

import { Col } from "@/shared/components/container";
import { FILE_OBJECT_KIND } from "@/shared/config/constants";
import { QSP } from "@/shared/config/qsp";
import { useTitle } from "@/shared/hooks/useTitle";

import { FilePreviewCard } from "@/entities/nodes/object/ui/object-details/file-preview-card";
import { ObjectActivitiesCard } from "@/entities/nodes/object/ui/object-details/object-activities-card";
import { ObjectDetailsCard } from "@/entities/nodes/object/ui/object-details/object-details-card";
import { ObjectProfilesGroupsCard } from "@/entities/nodes/object/ui/object-details/object-profiles-groups-card";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { ObjectDetailsTabContent } from "@/entities/nodes/relationships/ui/object-details-tab-content";
import type { NodeFileObject, NodeObjectWithMetadata } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

interface ObjectDetailsProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
}

const FILE_EXCLUDE_ATTRIBUTES = ["file_name", "file_size", "file_type", "storage_id", "checksum"];

export function ObjectDetails({ objectSchema, objectData, permission }: ObjectDetailsProps) {
  const [qspTab] = useQueryState(QSP.TAB);
  useTitle(`${getNodeLabel(objectData)} details`);

  if (qspTab) {
    return (
      <ObjectDetailsTabContent
        objectSchema={objectSchema}
        objectDetailsData={objectData}
        permission={permission}
      />
    );
  }

  const hasFileData = isOfKind(FILE_OBJECT_KIND, objectSchema);

  return (
    <div className="flex flex-col gap-2 overflow-auto p-2 xl:grid xl:grid-cols-3 xl:items-start">
      <Col className="shrink-0 grow md:col-span-2">
        <ObjectDetailsCard
          objectSchema={objectSchema}
          objectData={objectData}
          permission={permission}
          excludeAttributes={hasFileData ? FILE_EXCLUDE_ATTRIBUTES : undefined}
        />

        {hasFileData && <FilePreviewCard objectData={objectData as unknown as NodeFileObject} />}
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
