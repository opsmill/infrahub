import { useParams } from "react-router";

import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import type { Permission } from "@/entities/permission/domain/model/permission";
import type {
  NumberPoolData,
  NumberPoolDivisionSelector,
} from "@/entities/resource-manager/domain/model/number-pool";
import { useNumberPoolDivision } from "@/entities/resource-manager/ui/hooks/use-number-pool-division";
import { NumberPoolAllocationsCard } from "@/entities/resource-manager/ui/number-pool/details/number-pool-allocations-card";
import { NumberPoolDivisionCard } from "@/entities/resource-manager/ui/number-pool/details/number-pool-division-card";
import { NumberPoolDivisionInvalid } from "@/entities/resource-manager/ui/number-pool/details/number-pool-division-invalid";
import { NumberPoolDivisionsList } from "@/entities/resource-manager/ui/number-pool/details/number-pool-divisions-list";
import {
  NumberPoolHeader,
  NumberPoolHeaderSkeleton,
} from "@/entities/resource-manager/ui/number-pool/details/number-pool-header";
import { NumberPoolRangesCard } from "@/entities/resource-manager/ui/number-pool/details/number-pool-ranges-card";
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
      {pool.allocation_scope.value.length > 0 ? (
        <ScopedNumberPoolBody pool={pool} />
      ) : (
        <NumberPoolBody pool={pool} />
      )}
    </Content.Card>
  );
}

interface NumberPoolBodyProps {
  pool: NumberPoolData;
  division?: NumberPoolDivisionSelector;
}

function NumberPoolBody({ pool, division }: NumberPoolBodyProps) {
  const { rangeId } = useParams<{ rangeId?: string }>();
  const {
    data: utilization,
    error,
    isPending,
  } = useGetNumberPoolUtilization({
    poolId: pool.id,
    division,
  });

  if (isPending) return <LoadingIndicator className="flex-1" />;

  if (error) return <ErrorScreen message={error.message} />;

  return (
    <Row className="min-h-0 items-start px-2 pb-2">
      <Col className="min-h-0 w-80 shrink-0 gap-2">
        {division && <NumberPoolDivisionCard pool={pool} division={division} />}
        <NumberPoolRangesCard
          poolId={pool.id}
          poolType={pool.pool_type.value}
          utilization={utilization}
          selectedRangeId={rangeId ?? null}
        />
      </Col>

      <NumberPoolAllocationsCard
        poolId={pool.id}
        nodeKind={pool.node.value}
        nodeAttribute={pool.node_attribute.value}
        ranges={utilization.ranges}
        selectedRangeId={rangeId ?? null}
        division={division}
      />
    </Row>
  );
}

interface ScopedNumberPoolBodyProps {
  pool: NumberPoolData;
}

function ScopedNumberPoolBody({ pool }: ScopedNumberPoolBodyProps) {
  const division = useNumberPoolDivision(pool.allocation_scope.value);

  if (division.status === "none") {
    return <NumberPoolDivisionsList pool={pool} />;
  }

  if (division.status === "invalid") {
    return <NumberPoolDivisionInvalid pool={pool} cause={division.cause} />;
  }

  return <NumberPoolBody pool={pool} division={division.selector} />;
}
