import { useNavigate } from "react-router";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { IpPoolData } from "@/entities/resource-manager/domain/model/ip-pool";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/domain/model/pool";
import { PoolActionsMenu } from "@/entities/resource-manager/ui/pool/pool-actions-menu";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export interface IpPoolActionsMenuProps {
  pool: IpPoolData;
  schema: ModelSchema;
  permission: Permission;
}

export function IpPoolActionsMenu({ pool, schema, permission }: IpPoolActionsMenuProps) {
  const navigate = useNavigate();

  return (
    <PoolActionsMenu
      pool={pool}
      poolKind={pool.__typename}
      schema={schema}
      updateDecision={permission.update}
      deleteDecision={permission.delete}
      onDeleted={() => navigate(getObjectDetailsUrl(RESOURCE_GENERIC_KIND))}
    />
  );
}
