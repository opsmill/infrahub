import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { ObjectDetails } from "@/entities/nodes/object/ui/object-details/object-details";
import { ObjectDetailsTabs } from "@/entities/nodes/object/ui/object-details/object-details-tabs";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

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

  return (
    <>
      <ObjectDetailsTabs objectSchema={objectSchema} objectData={objectData} />
      <ObjectDetails objectSchema={objectSchema} objectData={objectData} permission={permission} />
    </>
  );
}
