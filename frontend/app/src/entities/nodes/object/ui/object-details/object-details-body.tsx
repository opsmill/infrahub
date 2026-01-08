import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { FILE_ATTACHMENT_KIND } from "@/shared/config/constants";

import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { FileAttachmentDetails } from "@/entities/nodes/object/ui/object-details/file-attachment-details";
import { ObjectDetails } from "@/entities/nodes/object/ui/object-details/object-details";
import { ObjectDetailsTabs } from "@/entities/nodes/object/ui/object-details/object-details-tabs";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

interface ObjectDetailsBodyProps {
  objectId: string;
  objectSchema: ModelSchema;
  permission: Permission;
}

export function ObjectDetailsBody({ objectSchema, objectId, permission }: ObjectDetailsBodyProps) {
  const { data: objectData, isPending, error } = useGetObject({ objectSchema, objectId });

  if (isPending) {
    return <LoadingIndicator className="h-full" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const isFileAttachment = isOfKind(FILE_ATTACHMENT_KIND, objectSchema);
  console.log("isFileAttachment: ", isFileAttachment);

  return (
    <>
      <ObjectDetailsTabs objectSchema={objectSchema} objectData={objectData} />
      {isFileAttachment ? (
        <FileAttachmentDetails
          objectSchema={objectSchema}
          objectData={objectData}
          permission={permission}
        />
      ) : (
        <ObjectDetails
          objectSchema={objectSchema}
          objectData={objectData}
          permission={permission}
        />
      )}
    </>
  );
}
