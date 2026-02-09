import { useQueryState } from "nuqs";

import { Col } from "@/shared/components/container";
import type { DataViewerContentType } from "@/shared/components/data-viewer/types";
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

interface ObjectDetailsProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
}

// Type guard to check if a property is an attribute
function isAttribute(
  prop: unknown
): prop is { value: string | number | boolean | string[] | null } {
  return prop !== null && typeof prop === "object" && "value" in prop;
}

// Helper to safely get attribute value with type checking
function getAttributeValue<T>(
  prop: unknown,
  typeCheck: (value: unknown) => value is T
): T | undefined {
  return isAttribute(prop) && typeCheck(prop.value) ? prop.value : undefined;
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNumber(value: unknown): value is number {
  return typeof value === "number";
}

// Extract file-related data from object
function getFileData(objectData: NodeObjectWithMetadata) {
  const fileName = getAttributeValue(objectData.file_name, isString);
  const fileSize = getAttributeValue(objectData.file_size, isNumber);
  const contentType = getAttributeValue(objectData.file_type, isString) as DataViewerContentType;

  const hasFileData = !!(fileName || fileSize || contentType);
  const displayName = fileName || getAttributeValue(objectData.name, isString) || "Unnamed file";

  return {
    hasFileData,
    fileName: displayName,
    fileSize,
    contentType,
  };
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

  const { hasFileData, fileName, fileSize, contentType } = getFileData(objectData);

  return (
    <div className="flex flex-col gap-2 overflow-auto p-2 xl:grid xl:grid-cols-3 xl:items-start">
      <Col className="shrink-0 grow md:col-span-2">
        <ObjectDetailsCard
          objectSchema={objectSchema}
          objectData={objectData}
          permission={permission}
          excludeAttributes={hasFileData ? FILE_EXCLUDE_ATTRIBUTES : undefined}
        />

        {hasFileData && (
          <FilePreviewCard
            nodeId={objectData.id}
            fileName={fileName}
            fileSize={fileSize}
            contentType={contentType}
          />
        )}
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
