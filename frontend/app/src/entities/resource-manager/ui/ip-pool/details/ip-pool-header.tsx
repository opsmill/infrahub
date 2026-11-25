import { useAtomValue } from "jotai";
import { useNavigate } from "react-router";

import { RefreshButton } from "@/shared/components/buttons/refresh-button";
import { Col, Row } from "@/shared/components/container";
import { NodeId } from "@/shared/components/display/node-id";
import { Skeleton } from "@/shared/components/loading/skeleton";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { NodeMetadataPopover } from "@/entities/nodes/object/ui/metadata/node-metadata-popover";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { IpPoolData } from "@/entities/resource-manager/domain/model/ip-pool";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/domain/model/pool";
import { IpPoolDefaultFields } from "@/entities/resource-manager/ui/ip-pool/details/ip-pool-default-fields";
import { IpPoolExtraFieldsList } from "@/entities/resource-manager/ui/ip-pool/details/ip-pool-extra-fields";
import { PoolActionsMenu } from "@/entities/resource-manager/ui/pool/pool-actions-menu";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export interface IpPoolHeaderProps {
  pool: IpPoolData;
  schema: ModelSchema;
  permission: Permission;
}

export function IpPoolHeader({ pool, schema, permission }: IpPoolHeaderProps) {
  const { currentBranch } = useCurrentBranch();
  const atDate = useAtomValue(datetimeAtom);
  const navigate = useNavigate();
  const refreshedQueryKeys = [
    resourceManagerQueryKeys.all,
    objectQueryKeys.lists({ objectKind: pool.__typename, branchName: currentBranch.name, atDate }),
  ];

  return (
    <header className="px-3 pt-2 pb-4 text-sm">
      <Row className="mb-3 items-start">
        <Col className="min-w-0 grow gap-0">
          <Row className="gap-1">
            <h1 className="truncate font-bold text-xl" title={pool.name.value}>
              {pool.name.value}
            </h1>
            <NodeMetadataPopover objectKind={pool.__typename} objectId={pool.id} />
          </Row>
          {pool.description.value && (
            <p className="text-pretty text-foreground-muted">{pool.description.value}</p>
          )}
        </Col>

        <NodeId id={pool.id} className="h-8" />
        <RefreshButton queryKeys={refreshedQueryKeys} />
        <PoolActionsMenu
          pool={pool}
          poolKind={pool.__typename}
          schema={schema}
          updateDecision={permission.update}
          deleteDecision={permission.delete}
          onDeleted={() => navigate(getObjectDetailsUrl(RESOURCE_GENERIC_KIND))}
        />
      </Row>

      <Row className="no-scrollbar -m-0.5 flex-wrap gap-x-8 gap-y-3 overflow-auto p-0.5">
        <IpPoolDefaultFields pool={pool} />
        <IpPoolExtraFieldsList poolId={pool.id} schema={schema} />
      </Row>
    </header>
  );
}

export function IpPoolHeaderSkeleton() {
  return (
    <div role="status" aria-label="Loading IP pool" className="px-3 pt-2 pb-4">
      <Row className="mb-3 gap-4">
        <Skeleton className="h-7 w-72" />
        <Skeleton className="ml-auto h-8 w-24" />
      </Row>
      <Skeleton className="h-10 w-96" />
    </div>
  );
}
