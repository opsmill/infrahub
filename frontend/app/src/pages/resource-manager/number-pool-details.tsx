import { useParams } from "react-router";

import { Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import type { Permission } from "@/entities/permission/domain/model/permission";
import type { NumberPoolData } from "@/entities/resource-manager/domain/model/number-pool";
import { NumberPoolAllocationsCard } from "@/entities/resource-manager/ui/number-pool/number-pool-allocations-card";
import {
  NumberPoolHeader,
  NumberPoolHeaderSkeleton,
} from "@/entities/resource-manager/ui/number-pool/number-pool-header";
import { NumberPoolRangesCard } from "@/entities/resource-manager/ui/number-pool/number-pool-ranges-card";
import { useGetNumberPool } from "@/entities/resource-manager/ui/queries/get-number-pool.query";
import { useGetNumberPoolUtilization } from "@/entities/resource-manager/ui/queries/get-number-pool-utilization.query";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export interface NumberPoolDetailsPageProps {
  poolId: string;
  schema: ModelSchema;
  permission: Permission;
}

export function NumberPoolDetailsPage({ poolId, schema, permission }: NumberPoolDetailsPageProps) {
  const { data: pool, error, isPending } = useGetNumberPool(poolId);

  if (error) return <ErrorScreen message={error.message} />;

  if (isPending) {
    return (
      <Content.Card className="grow">
        <NumberPoolHeaderSkeleton />
      </Content.Card>
    );
  }

  return (
    <Content.Card className="grow">
      <NumberPoolHeader pool={pool} schema={schema} permission={permission} />
      <NumberPoolBody pool={pool} />
    </Content.Card>
  );
}

interface NumberPoolBodyProps {
  pool: NumberPoolData;
}

function NumberPoolBody({ pool }: NumberPoolBodyProps) {
  const { rangeId } = useParams<{ rangeId?: string }>();
  const { data: utilization, error, isPending } = useGetNumberPoolUtilization(pool.id);

  if (isPending) return <LoadingIndicator className="flex-1" />;

  if (error) return <ErrorScreen message={error.message} />;

  return (
    <Row className="min-h-0 items-start px-2 pb-2">
      <NumberPoolRangesCard
        poolId={pool.id}
        poolType={pool.pool_type.value}
        utilization={utilization}
        selectedRangeId={rangeId ?? null}
      />
      <NumberPoolAllocationsCard
        poolId={pool.id}
        nodeKind={pool.node.value}
        nodeAttribute={pool.node_attribute.value}
        ranges={utilization.ranges}
        selectedRangeId={rangeId ?? null}
      />
    </Row>
  );
}
