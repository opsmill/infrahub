import { useParams } from "react-router";

import { IpPoolDetailsPage } from "@/pages/resource-manager/ip-pool-details";
import { NumberPoolDetailsPage } from "@/pages/resource-manager/number-pool-details";

import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import {
  IP_ADDRESS_POOL,
  IP_PREFIX_POOL,
  NUMBER_POOL_KIND,
  RESOURCE_GENERIC_KIND,
} from "@/entities/resource-manager/domain/model/pool";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function Component() {
  const { resourcePoolId } = useParams();
  const { schema: genericPoolSchema } = useSchema(RESOURCE_GENERIC_KIND);

  const { data, error, isPending } = useGetObject({
    objectSchema: genericPoolSchema!,
    objectId: resourcePoolId!,
    getAttributesVisible: () => [],
    getRelationshipsVisible: () => [],
  });

  if (isPending) return <LoadingIndicator className="h-full" />;

  if (error && !data) return <ErrorScreen message={error.message} />;

  return (
    <ResourcePoolDetailsPage resourcePoolId={resourcePoolId!} resourcePoolKind={data.__typename} />
  );
}

interface ResourcePoolDetailsPageProps {
  resourcePoolId: string;
  resourcePoolKind: string;
}

function ResourcePoolDetailsPage({
  resourcePoolId,
  resourcePoolKind,
}: ResourcePoolDetailsPageProps) {
  const { schema } = useSchema(resourcePoolKind);

  if (!schema) return <NoDataFound />;

  return (
    <RequireObjectPermissions objectKind={schema.kind}>
      {({ permission }) => {
        switch (schema.kind) {
          case NUMBER_POOL_KIND:
            return (
              <NumberPoolDetailsPage
                poolId={resourcePoolId}
                schema={schema}
                permission={permission}
              />
            );
          case IP_PREFIX_POOL:
          case IP_ADDRESS_POOL:
            return (
              <IpPoolDetailsPage poolId={resourcePoolId} schema={schema} permission={permission} />
            );
          default:
            return <NoDataFound />;
        }
      }}
    </RequireObjectPermissions>
  );
}
