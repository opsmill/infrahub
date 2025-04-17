import { TASK_OBJECT } from "@/config/constants";
import { useObjectDetails } from "@/entities/nodes/hooks/useObjectDetails";
import ObjectItemDetails from "@/entities/nodes/object-item-details/object-item-details-paginated";
import { ModelSchema } from "@/entities/schema/types";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { NetworkStatus } from "@apollo/client";
import { Permission } from "@/entities/permission/types";

export interface ObjectDetailsProps {
  objectId: string;
  objectSchema: ModelSchema;
  permission: Permission;
}

export function ObjectDetails({ objectSchema, objectId, permission }: ObjectDetailsProps) {
  const { data, networkStatus, error } = useObjectDetails(objectSchema, objectId);

  if (networkStatus === NetworkStatus.loading) {
    return <LoadingIndicator className="h-[calc(100vh-10.5rem)]" />;
  }

  if (!permission.view.isAllowed) {
    return <UnauthorizedScreen message={permission.view.message} />;
  }

  if (error) {
    if (error.networkError?.statusCode === 403) {
      const { message } = error.networkError?.result?.errors?.[0] ?? {};

      return <UnauthorizedScreen message={message} />;
    }

    return <ErrorScreen message="Something went wrong when fetching the object details." />;
  }

  const objectDetailsData = objectSchema && data && data[objectSchema.kind!]?.edges[0]?.node;

  if (!objectDetailsData) {
    return (
      <div className="flex column justify-center">
        <NoDataFound message={`No ${objectSchema.label} found with ID: ${objectId}`} />
      </div>
    );
  }

  return (
    <ObjectItemDetails
      schema={objectSchema}
      objectDetailsData={objectDetailsData}
      permission={permission}
      taskData={data[TASK_OBJECT]}
    />
  );
}
