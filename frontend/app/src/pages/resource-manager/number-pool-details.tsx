import { ResourcePoolDetailsBody } from "@/pages/resource-manager/resource-pool-details-body";

import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";

import type { Permission } from "@/entities/permission/domain/model/permission";
import {
  NumberPoolHeader,
  NumberPoolHeaderSkeleton,
} from "@/entities/resource-manager/ui/number-pool/number-pool-header";
import { useGetNumberPool } from "@/entities/resource-manager/ui/queries/get-number-pool.query";
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
      <Content.Card>
        <NumberPoolHeaderSkeleton />
        <ResourcePoolDetailsBody poolId={poolId} schema={schema} permission={permission} />
      </Content.Card>
    );
  }

  return (
    <Content.Card>
      <NumberPoolHeader pool={pool} schema={schema} permission={permission} />
      <ResourcePoolDetailsBody poolId={poolId} schema={schema} permission={permission} />
    </Content.Card>
  );
}
