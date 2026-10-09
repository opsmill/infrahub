import { Tooltip } from "@infrahub/ui";
import { FileCodeIcon } from "lucide-react";
import React from "react";
import { Button as AriaButton, DialogTrigger } from "react-aria-components";

import { CopyToClipboardButton } from "@/shared/components/buttons/copy-to-clipboard-button";
import { Col, Row } from "@/shared/components/container";
import { Skeleton } from "@/shared/components/loading/skeleton";
import { classNames } from "@/shared/utils/common";

import { NodeMetadataPopover } from "@/entities/nodes/object/ui/metadata/node-metadata-popover";
import { RefreshButton } from "@/entities/nodes/object/ui/object-details/refresh-button";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { NumberPoolData } from "@/entities/resource-manager/domain/model/number-pool";
import {
  NUMBER_POOL_KIND,
  NUMBER_POOL_TYPE_SCHEMA,
} from "@/entities/resource-manager/domain/model/pool";
import { NumberPoolActionsMenu } from "@/entities/resource-manager/ui/number-pool/number-pool-actions-menu";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { SchemaViewerModal } from "@/entities/schema/ui/schema-viewer-modal";

const managedByTagStyle =
  "inline-flex h-6 shrink-0 items-center gap-1 rounded-lg border border-border-strong px-2 font-medium text-foreground text-xs data-hovered:bg-highlight";

const schemaLinkStyle = "font-medium underline decoration-dotted data-hovered:decoration-solid";

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

interface PoolIdProps {
  id: string;
  className?: string;
}

function PoolId({ id, className }: PoolIdProps) {
  return (
    <Row className={classNames("min-w-0 gap-1 text-sm", className)}>
      <span className="shrink-0">ID</span>
      <span className="min-w-0 truncate font-mono text-foreground-muted text-xs">{id}</span>
      <CopyToClipboardButton data={id} aria-label="Copy ID" />
    </Row>
  );
}

interface SchemaReferenceProps {
  schema: ModelSchema | null;
  targetField?: string;
  className?: string;
  children: React.ReactNode;
}

function SchemaReference({ schema, targetField, className, children }: SchemaReferenceProps) {
  if (!schema) return <span className={classNames(className, "no-underline")}>{children}</span>;

  const isRelationship = schema.relationships?.some((field) => field.name === targetField);
  const fieldTab = isRelationship ? "relationships" : "attributes";
  const defaultTab = targetField ? fieldTab : undefined;

  return (
    <DialogTrigger>
      <AriaButton
        className={classNames(
          "cursor-pointer rounded-md outline-none data-focus-visible:ring-2 data-focus-visible:ring-ring-halo",
          className
        )}
      >
        {children}
      </AriaButton>
      <SchemaViewerModal schema={schema} defaultTab={defaultTab} targetField={targetField} />
    </DialogTrigger>
  );
}

interface ScopeFieldReferenceProps {
  schema: ModelSchema | null;
  fieldName: string;
}

function ScopeFieldReference({ schema, fieldName }: ScopeFieldReferenceProps) {
  const fieldSchema = [...(schema?.attributes ?? []), ...(schema?.relationships ?? [])].find(
    (field) => field.name === fieldName
  );

  return (
    <SchemaReference
      schema={fieldSchema ? schema : null}
      targetField={fieldName}
      className={schemaLinkStyle}
    >
      {fieldSchema?.label || fieldName}
    </SchemaReference>
  );
}

interface AllocationSentenceProps {
  pool: NumberPoolData;
}

function AllocationSentence({ pool }: AllocationSentenceProps) {
  const kind = pool.node.value;
  const attribute = pool.node_attribute.value;
  const { schema } = useSchema(kind);
  const scopeFields = pool.allocation_scope.value;

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
      {scopeFields.length === 0 ? (
        <span className="text-foreground-muted">with no scope</span>
      ) : (
        <>
          <span className="text-foreground-muted">scoped by</span>
          {scopeFields.map((fieldName, index) => (
            <React.Fragment key={fieldName}>
              {index > 0 && <span className="text-foreground-muted">+</span>}
              <ScopeFieldReference schema={schema} fieldName={fieldName} />
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
        <RefreshButton queryKey={resourceManagerQueryKeys.all} />
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
