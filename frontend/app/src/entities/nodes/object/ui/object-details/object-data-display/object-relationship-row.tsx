import { Button, Tooltip } from "@infrahub/ui";
import { LockIcon } from "lucide-react";

import { Row } from "@/shared/components/container";
import { Icon } from "@/shared/components/display/icon";
import MetaDetailsTooltip from "@/shared/components/display/meta-details-tooltips";
import { Link } from "@/shared/components/ui/link";

import type {
  NodeRelationshipManyWithMetadata,
  NodeRelationshipOneWithMetadata,
  NodeRelationshipWithMetadata,
} from "@/entities/nodes/object/domain/model/node";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { ExtraFieldIndicator } from "@/entities/nodes/object/ui/object-details/object-data-display/extra-field-indicator";
import { ObjectDataRow } from "@/entities/nodes/object/ui/object-details/object-data-display/object-data-row";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { RelationshipSchema } from "@/entities/schema/domain/model/schema";
import { getRelationshipLabel } from "@/entities/schema/domain/rules/get-relationship-label";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface ObjectRelationshipRowProps {
  relationshipSchema: RelationshipSchema;
  relationshipData: NodeRelationshipWithMetadata;
  permission: Permission;
  objectKind: string;
  onClickMetadata?: (relationship: RelationshipSchema) => void;
}

export function ObjectRelationshipRow({
  relationshipSchema,
  relationshipData,
  permission,
  objectKind,
  onClickMetadata,
}: ObjectRelationshipRowProps) {
  if (relationshipSchema.cardinality === "one") {
    return (
      <RelationshipOneRow
        relationshipSchema={relationshipSchema}
        relationshipData={relationshipData as NodeRelationshipOneWithMetadata}
        permission={permission}
        objectKind={objectKind}
        onClickMetadata={onClickMetadata}
      />
    );
  }

  return (
    <RelationshipManyRow
      relationshipData={relationshipData as NodeRelationshipManyWithMetadata}
      relationshipSchema={relationshipSchema}
      objectKind={objectKind}
    />
  );
}

interface RelationshipOneRowProps {
  relationshipSchema: RelationshipSchema;
  relationshipData: NodeRelationshipOneWithMetadata;
  permission: Permission;
  objectKind: string;
  onClickMetadata?: (relationship: RelationshipSchema) => void;
}

function RelationshipOneRow({
  relationshipSchema,
  relationshipData,
  permission,
  objectKind,
  onClickMetadata,
}: RelationshipOneRowProps) {
  const relatedNode = relationshipData.node;
  const relationshipProperties = relationshipData.properties;
  const { schema: peerSchema } = useSchema(relationshipSchema.peer);

  return (
    <ObjectDataRow
      fieldSchema={relationshipSchema}
      objectKind={objectKind}
      value={
        <>
          {relatedNode ? (
            <Link to={getObjectDetailsUrl(relatedNode.__typename, relatedNode.id)}>
              {getNodeLabel(relatedNode)}
            </Link>
          ) : (
            "-"
          )}

          {relationshipProperties && (
            <>
              {relationshipProperties.is_protected && (
                <LockIcon className="size-3.5 text-foreground-muted" />
              )}
              <MetaDetailsTooltip
                updatedAt={relationshipProperties.updated_at}
                source={relationshipProperties.source}
                owner={relationshipProperties.owner}
                isProtected={relationshipProperties.is_protected}
                triggerClassName="opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
                header={
                  onClickMetadata && (
                    <div className="flex items-center justify-between border-b p-1 pt-0 pl-2">
                      <div className="font-semibold">
                        {getRelationshipLabel(relationshipSchema, peerSchema)}
                      </div>

                      <Tooltip message={permission.update.message ?? undefined}>
                        <Button
                          variant="ghost"
                          size="xs"
                          shape="circle"
                          isDisabledAndFocusable={!permission.update.isAllowed}
                          onPress={() => onClickMetadata(relationshipSchema)}
                          data-testid="edit-metadata-button"
                        >
                          <Icon icon="mdi:pencil" className="text-custom-blue-500" />
                        </Button>
                      </Tooltip>
                    </div>
                  )
                }
              />
            </>
          )}

          {relationshipSchema.display === "extra" && <ExtraFieldIndicator className="ml-auto" />}
        </>
      }
    />
  );
}

interface RelationshipManyRowProps {
  relationshipData: NodeRelationshipManyWithMetadata;
  relationshipSchema: RelationshipSchema;
  objectKind: string;
}

function RelationshipManyRow({
  relationshipData,
  relationshipSchema,
  objectKind,
}: RelationshipManyRowProps) {
  const relatedNodeEdges = relationshipData.edges;
  const isExtraField = relationshipSchema.display === "extra";

  if (relatedNodeEdges.length === 0) {
    return (
      <ObjectDataRow
        fieldSchema={relationshipSchema}
        objectKind={objectKind}
        value={<>-{isExtraField && <ExtraFieldIndicator className="ml-auto" />}</>}
      />
    );
  }

  return (
    <ObjectDataRow
      fieldSchema={relationshipSchema}
      objectKind={objectKind}
      value={
        <>
          <dl className="flex w-full flex-col">
            {relatedNodeEdges.map((edge) => {
              const relatedNode = edge.node;
              const edgeProperties = edge.properties;

              if (!relatedNode) return null;

              return (
                <Row key={relatedNode.id} className="group/edge w-full">
                  <Link to={getObjectDetailsUrl(relatedNode.__typename, relatedNode.id)}>
                    {getNodeLabel(relatedNode)}
                  </Link>

                  {edgeProperties && (
                    <>
                      {edgeProperties.is_protected && (
                        <LockIcon className="size-3.5 text-foreground-muted" />
                      )}
                      <MetaDetailsTooltip
                        updatedAt={edgeProperties.updated_at}
                        source={edgeProperties.source}
                        owner={edgeProperties.owner}
                        isProtected={edgeProperties.is_protected}
                        triggerClassName="opacity-0 transition-opacity group-hover/edge:opacity-100 focus-visible:opacity-100"
                      />
                    </>
                  )}
                </Row>
              );
            })}
          </dl>

          {isExtraField && <ExtraFieldIndicator className="ml-auto" />}
        </>
      }
    />
  );
}
