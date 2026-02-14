import { Icon } from "@iconify-icon/react";
import { LockIcon } from "lucide-react";

import { Row } from "@/shared/components/container";
import MetaDetailsTooltip from "@/shared/components/display/meta-details-tooltips";
import { ButtonWithTooltip } from "@/shared/components/ui/button";
import { Link } from "@/shared/components/ui/link";

import { ObjectDataRow } from "@/entities/nodes/object/ui/object-details/object-data-display/object-data-row";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type {
  NodeRelationshipManyWithMetadata,
  NodeRelationshipOneWithMetadata,
  NodeRelationshipWithMetadata,
} from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { Permission } from "@/entities/permission/types";
import type { RelationshipSchema } from "@/entities/schema/types";

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
              <MetaDetailsTooltip
                updatedAt={relationshipProperties.updated_at}
                source={relationshipProperties.source}
                owner={relationshipProperties.owner}
                isProtected={relationshipProperties.is_protected}
                header={
                  onClickMetadata && (
                    <div className="flex items-center justify-between border-gray-200 border-b p-1 pt-0 pl-2">
                      <div className="font-semibold">{relationshipSchema.label}</div>

                      <ButtonWithTooltip
                        variant="ghost"
                        size="icon"
                        disabled={!permission.update.isAllowed}
                        tooltipEnabled={!permission.update.isAllowed}
                        tooltipContent={permission.update.message ?? undefined}
                        onClick={() => onClickMetadata(relationshipSchema)}
                        data-testid="edit-metadata-button"
                      >
                        <Icon icon="mdi:pencil" className="text-custom-blue-500" />
                      </ButtonWithTooltip>
                    </div>
                  )
                }
              />
              {relationshipProperties.is_protected && (
                <LockIcon className="size-3.5 text-gray-600" />
              )}
            </>
          )}
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

  if (relatedNodeEdges.length === 0) {
    return <ObjectDataRow fieldSchema={relationshipSchema} objectKind={objectKind} value="-" />;
  }

  return (
    <ObjectDataRow
      fieldSchema={relationshipSchema}
      objectKind={objectKind}
      value={
        <dl className="flex flex-col">
          {relatedNodeEdges.map((edge) => {
            const relatedNode = edge.node;
            const edgeProperties = edge.properties;

            if (!relatedNode) return null;

            return (
              <Row key={relatedNode.id}>
                <Link to={getObjectDetailsUrl(relatedNode.__typename, relatedNode.id)}>
                  {getNodeLabel(relatedNode)}
                </Link>

                {edgeProperties && (
                  <>
                    <MetaDetailsTooltip
                      updatedAt={edgeProperties.updated_at}
                      source={edgeProperties.source}
                      owner={edgeProperties.owner}
                      isProtected={edgeProperties.is_protected}
                    />
                    {edgeProperties.is_protected && <LockIcon className="size-3.5 text-gray-600" />}
                  </>
                )}
              </Row>
            );
          })}
        </dl>
      }
    />
  );
}
