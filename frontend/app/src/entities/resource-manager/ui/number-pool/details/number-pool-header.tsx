import { Tooltip } from "@infrahub/ui";
import { FileCodeIcon } from "lucide-react";
import React from "react";

import { RefreshButton } from "@/shared/components/buttons/refresh-button";
import { Col, Row } from "@/shared/components/container";
import { Skeleton } from "@/shared/components/loading/skeleton";

import { NodeMetadataPopover } from "@/entities/nodes/object/ui/metadata/node-metadata-popover";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { NumberPoolData } from "@/entities/resource-manager/domain/model/number-pool";
import {
  NUMBER_POOL_KIND,
  NUMBER_POOL_TYPE_SCHEMA,
} from "@/entities/resource-manager/domain/model/pool";
import { useAllocationScopeFields } from "@/entities/resource-manager/ui/hooks/use-allocation-scope-fields";
import { NumberPoolActionsMenu } from "@/entities/resource-manager/ui/number-pool/details/number-pool-actions-menu";
import { PoolId } from "@/entities/resource-manager/ui/pool/pool-id";
import {
  SchemaReference,
  schemaLinkStyle,
} from "@/entities/resource-manager/ui/pool/schema-reference";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

const REFRESHED_QUERY_KEYS = [resourceManagerQueryKeys.all];

const managedByTagStyle =
  "inline-flex h-6 shrink-0 items-center gap-1 rounded-lg border border-border-strong px-2 font-medium text-foreground text-xs data-hovered:bg-highlight";

interface ManagedBySchemaTagProps {
  pool: NumberPoolData;
}

function ManagedBySchemaTag({ pool }: ManagedBySchemaTagProps) {
  const kind = pool.node.value;
  const attribute = pool.node_attribute.value;
  const { schema: kindSchema } = useSchema(kind);

  if (pool.pool_type.value !== NUMBER_POOL_TYPE_SCHEMA) return null;

  return (
    <Tooltip
      message={`Created from the ${kind}.${attribute} schema attribute. Change its ranges in the schema.`}
      nonInteractiveTrigger={!kindSchema}
    >
      <SchemaReference schema={kindSchema} targetField={attribute} className={managedByTagStyle}>
        <FileCodeIcon className="size-3.5 text-foreground-muted" aria-hidden />
        Managed by schema
      </SchemaReference>
    </Tooltip>
  );
}

interface AllocationSentenceProps {
  pool: NumberPoolData;
}

function AllocationSentence({ pool }: AllocationSentenceProps) {
  const kind = pool.node.value;
  const attribute = pool.node_attribute.value;
  const { schema } = useSchema(kind);
  const allocationScopeFields = useAllocationScopeFields(pool);

  return (
    <Row className="flex-wrap gap-1.5 text-sm">
      <span className="text-foreground-muted">Allocates to</span>
      <SchemaReference schema={schema} className={schemaLinkStyle}>
        {kind}
      </SchemaReference>
      <span className="text-foreground-muted">attribute</span>
      <SchemaReference schema={schema} className={schemaLinkStyle} targetField={attribute}>
        {attribute}
      </SchemaReference>
      {allocationScopeFields.length > 0 && (
        <>
          <span className="text-foreground-muted">scoped by</span>
          {allocationScopeFields.map((field, index) => (
            <React.Fragment key={field.name}>
              {index > 0 && <span className="text-foreground-muted">+</span>}
              <SchemaReference schema={schema} className={schemaLinkStyle} targetField={field.name}>
                {field.label}
              </SchemaReference>
            </React.Fragment>
          ))}
        </>
      )}
    </Row>
  );
}

export interface NumberPoolHeaderProps {
  pool: NumberPoolData;
  schema: ModelSchema;
  permission: Permission;
}

export function NumberPoolHeader({ pool, schema, permission }: NumberPoolHeaderProps) {
  return (
    <header className="px-3 py-2 text-sm">
      <Row className="mb-4 items-start">
        <Col className="min-w-0 grow gap-0">
          <Row className="min-w-0 gap-1">
            <h1 className="min-w-0 truncate font-bold text-xl" title={pool.name.value}>
              {pool.name.value}
            </h1>
            <NodeMetadataPopover objectKind={NUMBER_POOL_KIND} objectId={pool.id} />
            <ManagedBySchemaTag pool={pool} />
          </Row>
          {pool.description.value && (
            <p className="text-pretty text-foreground-muted">{pool.description.value}</p>
          )}
        </Col>

        <PoolId id={pool.id} className="h-8" />
        <RefreshButton queryKeys={REFRESHED_QUERY_KEYS} />
        <NumberPoolActionsMenu pool={pool} schema={schema} permission={permission} />
      </Row>

      <AllocationSentence pool={pool} />
    </header>
  );
}

export function NumberPoolHeaderSkeleton() {
  return (
    <Row role="status" aria-label="Loading number pool" className="gap-4 px-3 py-2">
      <Skeleton className="h-7 w-72" />
      <Skeleton className="ml-auto h-8 w-24" />
    </Row>
  );
}
