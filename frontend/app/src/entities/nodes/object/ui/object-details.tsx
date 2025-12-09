import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { ObjectDetailsTabs } from "@/entities/nodes/object/ui/object-details/object-details-tabs";
import { ObjectItemDetails } from "@/entities/nodes/object-item-details/object-item-details";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

export interface ObjectDetailsProps {
  objectId: string;
  objectSchema: ModelSchema;
  permission: Permission;
}

export function ObjectDetails({ objectSchema, objectId, permission }: ObjectDetailsProps) {
  const { data: objectDetailsData, isPending, error } = useGetObject({ objectSchema, objectId });

  if (isPending) {
    return <LoadingIndicator className="h-[calc(100vh-10.5rem)]" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  return (
    <>
      <ObjectDetailsTabs
        schema={objectSchema}
        objectData={objectDetailsData}
        permission={permission}
      />
      <ObjectItemDetails
        objectSchema={objectSchema}
        objectData={objectDetailsData}
        permission={permission}
      />
    </>
  );
}
