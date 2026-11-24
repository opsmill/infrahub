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
import { IpPoolDefaultsLine } from "@/entities/resource-manager/ui/ip-pool/details/ip-pool-defaults-line";
import { IpPoolExtraFieldsLine } from "@/entities/resource-manager/ui/ip-pool/details/ip-pool-extra-fields";
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
  const refreshedQueryKeys = [
    resourceManagerQueryKeys.all,
    objectQueryKeys.lists({ objectKind: pool.__typename, branchName: currentBranch.name, atDate }),
  ];
  const navigate = useNavigate();

  return (
    <header className="px-3 py-2 text-sm">
      <Row className="mb-4 items-start">
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

      <IpPoolDefaultsLine pool={pool} poolLabel={schema.label ?? schema.kind!} />
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
