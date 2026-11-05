import { RefreshButton } from "@/shared/components/buttons/refresh-button";
import { Col, Row } from "@/shared/components/container";
import { Skeleton } from "@/shared/components/loading/skeleton";

import { NodeMetadataPopover } from "@/entities/nodes/object/ui/metadata/node-metadata-popover";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { IpPoolData } from "@/entities/resource-manager/domain/model/ip-pool";
import { IpPoolActionsMenu } from "@/entities/resource-manager/ui/ip-pool/details/ip-pool-actions-menu";
import { IpPoolDefaultsLine } from "@/entities/resource-manager/ui/ip-pool/details/ip-pool-defaults-line";
import { IpPoolExtraFieldsLine } from "@/entities/resource-manager/ui/ip-pool/details/ip-pool-extra-fields";
import { PoolId } from "@/entities/resource-manager/ui/pool/pool-id";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

const REFRESHED_QUERY_KEYS = [resourceManagerQueryKeys.all];

export interface IpPoolHeaderProps {
  pool: IpPoolData;
  schema: ModelSchema;
  permission: Permission;
}

export function IpPoolHeader({ pool, schema, permission }: IpPoolHeaderProps) {
  return (
    <header className="px-3 py-2 text-sm">
      <Row className="mb-4 items-start">
        <Col className="min-w-0 grow gap-0">
          <Row className="min-w-0 gap-1">
            <h1 className="min-w-0 truncate font-bold text-xl" title={pool.name.value}>
              {pool.name.value}
            </h1>
            <NodeMetadataPopover objectKind={pool.__typename} objectId={pool.id} />
          </Row>
          {pool.description.value && (
            <p className="text-pretty text-foreground-muted">{pool.description.value}</p>
          )}
        </Col>

        <PoolId id={pool.id} className="h-8" />
        <RefreshButton queryKeys={REFRESHED_QUERY_KEYS} />
        <IpPoolActionsMenu pool={pool} schema={schema} permission={permission} />
      </Row>

      <IpPoolDefaultsLine pool={pool} />
      <IpPoolExtraFieldsLine poolId={pool.id} schema={schema} />
    </header>
  );
}

export function IpPoolHeaderSkeleton() {
  return (
    <Row role="status" aria-label="Loading IP pool" className="gap-4 px-3 py-2">
      <Skeleton className="h-7 w-72" />
      <Skeleton className="ml-auto h-8 w-24" />
    </Row>
  );
}
