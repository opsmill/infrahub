import { Card } from "@infrahub/ui";
import { Outlet } from "react-router";

import { Col } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { ObjectDetailsTabs } from "@/entities/nodes/object/ui/object-details/object-details-tabs";
import type { ObjectDetailsOutletContext } from "@/entities/nodes/object/ui/object-details/use-object-details-outlet";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
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
    <Col className="gap-0 overflow-auto p-1">
      <ObjectDetailsTabs objectSchema={objectSchema} objectData={objectData} />
      <Card className="overflow-auto to-neutral-50">
        <Outlet
          context={{ objectSchema, objectData, permission } satisfies ObjectDetailsOutletContext}
        />
      </Card>
    </Col>
  );
}
