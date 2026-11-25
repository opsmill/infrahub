import { useParams } from "react-router";

import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import type { Permission } from "@/entities/permission/domain/model/permission";
import type { IpPoolKind } from "@/entities/resource-manager/domain/model/pool";
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
  poolKind: IpPoolKind;
  schema: ModelSchema;
  permission: Permission;
}

export function IpPoolDetailsPage({
  poolId,
  poolKind,
  schema,
  permission,
}: IpPoolDetailsPageProps) {
  const { data: pool, error, isPending } = useGetIpPool({ poolId, poolKind });

  if (error && !pool) return <ErrorScreen message={error.message} />;

  return (
    <Content.Card className="grow">
      {isPending ? (
        <IpPoolHeaderSkeleton />
      ) : (
        <IpPoolHeader pool={pool} schema={schema} permission={permission} />
      )}
      <IpPoolBody poolId={poolId} poolKind={poolKind} />
    </Content.Card>
  );
}

interface IpPoolBodyProps {
  poolId: string;
  poolKind: IpPoolKind;
}

function IpPoolBody({ poolId, poolKind }: IpPoolBodyProps) {
  const { resourceId } = useParams<{ resourceId?: string }>();
  const { data: utilization, error, isPending } = useGetIpPoolUtilization(poolId);

  if (isPending) return <LoadingIndicator className="flex-1" />;

  if (error && !utilization) return <ErrorScreen message={error.message} />;

  const { usage, resources, areWeightsUnavailable } = utilization;
  const selectedResourceId = resourceId ?? null;

  return (
    <Row className="min-h-0 items-start px-2 pb-2">
      <Col className="max-h-full min-h-0 w-80 shrink-0">
        <IpPoolResourcesCard
          poolId={poolId}
          poolKind={poolKind}
          usage={usage}
          resources={resources}
          areWeightsUnavailable={areWeightsUnavailable}
          selectedResourceId={selectedResourceId}
        />
      </Col>

      <IpPoolAllocationsCard
        poolId={poolId}
        poolKind={poolKind}
        resources={resources}
        selectedResourceId={selectedResourceId}
      />
    </Row>
  );
}
