import { useParams } from "react-router";

import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import type { Permission } from "@/entities/permission/domain/model/permission";
import type { IpPoolData } from "@/entities/resource-manager/domain/model/ip-pool";
import { IpPoolAllocationsCard } from "@/entities/resource-manager/ui/ip-pool/details/ip-pool-allocations-card";
import {
  IpPoolHeader,
  IpPoolHeaderSkeleton,
} from "@/entities/resource-manager/ui/ip-pool/details/ip-pool-header";
import { IpPoolResourcesCard } from "@/entities/resource-manager/ui/ip-pool/details/ip-pool-resources-card";
import { useGetIpPool } from "@/entities/resource-manager/ui/queries/get-ip-pool.query";
import { useGetIpPoolUtilization } from "@/entities/resource-manager/ui/queries/get-ip-pool-utilization.query";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export interface IpPoolDetailsPageProps {
  poolId: string;
  schema: ModelSchema;
  permission: Permission;
}

export function IpPoolDetailsPage({ poolId, schema, permission }: IpPoolDetailsPageProps) {
  const { data: pool, error, isPending } = useGetIpPool(poolId);
  // requested here so it loads alongside the pool instead of after it
  const utilizationQuery = useGetIpPoolUtilization(poolId);

  if (error) return <ErrorScreen message={error.message} />;

  if (isPending) {
    return (
      <Content.Card className="grow">
        <IpPoolHeaderSkeleton />
      </Content.Card>
    );
  }

  return (
    <Content.Card className="grow">
      <IpPoolHeader pool={pool} schema={schema} permission={permission} />
      <IpPoolBody pool={pool} utilizationQuery={utilizationQuery} />
    </Content.Card>
  );
}

interface IpPoolBodyProps {
  pool: IpPoolData;
  utilizationQuery: ReturnType<typeof useGetIpPoolUtilization>;
}

function IpPoolBody({ pool, utilizationQuery }: IpPoolBodyProps) {
  const { resourceId } = useParams<{ resourceId?: string }>();
  const { data: utilization, error, isPending } = utilizationQuery;

  if (isPending) return <LoadingIndicator className="flex-1" />;

  if (error) return <ErrorScreen message={error.message} />;

  const { usage, resources } = utilization;
  const selectedResourceId = resourceId ?? resources[0]?.id ?? null;

  return (
    <Row className="min-h-0 items-start px-2 pb-2">
      <Col className="min-h-0 w-80 shrink-0 gap-2">
        <IpPoolResourcesCard
          poolId={pool.id}
          poolKind={pool.__typename}
          usage={usage}
          resources={resources}
          selectedResourceId={selectedResourceId}
        />
      </Col>

      <IpPoolAllocationsCard
        poolId={pool.id}
        poolKind={pool.__typename}
        resources={resources}
        selectedResourceId={selectedResourceId}
      />
    </Row>
  );
}
