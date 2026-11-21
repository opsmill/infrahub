import { useNavigate } from "react-router";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { Permission, PermissionDecision } from "@/entities/permission/domain/model/permission";
import type { NumberPoolData } from "@/entities/resource-manager/domain/model/number-pool";
import {
  NUMBER_POOL_KIND,
  NUMBER_POOL_TYPE_SCHEMA,
} from "@/entities/resource-manager/domain/model/pool";
import { PoolActionsMenu } from "@/entities/resource-manager/ui/pool/pool-actions-menu";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export interface NumberPoolActionsMenuProps {
  pool: NumberPoolData;
  schema: ModelSchema;
  permission: Permission;
}

export function NumberPoolActionsMenu({ pool, schema, permission }: NumberPoolActionsMenuProps) {
  const navigate = useNavigate();

  const isSchemaManaged = pool.pool_type.value === NUMBER_POOL_TYPE_SCHEMA;
  const schemaLock: PermissionDecision = {
    isAllowed: false,
    message: `Defined by the schema attribute ${pool.node.value}.${pool.node_attribute.value}`,
  };

  return (
    <PoolActionsMenu
      pool={pool}
      poolKind={NUMBER_POOL_KIND}
      schema={schema}
      updateDecision={isSchemaManaged ? schemaLock : permission.update}
      deleteDecision={isSchemaManaged ? schemaLock : permission.delete}
      onDeleted={() => navigate(getObjectDetailsUrl(NUMBER_POOL_KIND))}
    />
  );
}
