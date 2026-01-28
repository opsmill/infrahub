import { useQueryState } from "nuqs";

import { Col } from "@/shared/components/container";
import { QSP } from "@/shared/config/qsp";
import { useTitle } from "@/shared/hooks/useTitle";

import { FilePreviewCard } from "@/entities/nodes/object/ui/object-details/file-preview-card";
import { ObjectActivitiesCard } from "@/entities/nodes/object/ui/object-details/object-activities-card";
import { ObjectDetailsCard } from "@/entities/nodes/object/ui/object-details/object-details-card";
import { ObjectProfilesGroupsCard } from "@/entities/nodes/object/ui/object-details/object-profiles-groups-card";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { ObjectDetailsTabContent } from "@/entities/nodes/relationships/ui/object-details-tab-content";
import type { NodeObjectWithMetadata } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

interface FileAttachmentDetailsProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
}

export function FileAttachmentDetails({
  objectSchema,
  objectData,
  permission,
}: FileAttachmentDetailsProps) {
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

  // Extract file-related attributes
  const storageId = objectData.storage_id?.value;
  const fileName = objectData.file_name?.value || objectData.name?.value || "Unnamed file";
  const fileSize = objectData.file_size?.value;
  const contentType = objectData.file_type?.value;

  return (
    <div className="flex flex-col gap-2 overflow-auto p-2 xl:grid xl:grid-cols-3 xl:items-start">
      <div className="flex flex-col gap-2 md:col-span-2">
        <ObjectDetailsCard
          objectSchema={objectSchema}
          objectData={objectData}
          permission={permission}
          className="shrink-0 grow overflow-x-hidden p-0"
          excludeAttributes={["file_name", "file_size", "file_type", "storage_id", "checksum"]}
        />

        <FilePreviewCard
          storageId={storageId}
          fileName={fileName}
          fileSize={fileSize}
          contentType={contentType}
        />
      </div>

      <Col>
        <ObjectProfilesGroupsCard
          objectSchema={objectSchema}
          objectData={objectData}
          permission={permission}
        />
        <ObjectActivitiesCard
          objectKind={objectData.__typename}
          objectId={objectData.id}
          className="overflow-x-hidden p-0"
        />
      </Col>
    </div>
  );
}
