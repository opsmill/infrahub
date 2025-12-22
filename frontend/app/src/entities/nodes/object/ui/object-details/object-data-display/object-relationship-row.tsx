import { Icon } from "@iconify-icon/react";
import { LockIcon } from "lucide-react";

import { ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import { Row } from "@/shared/components/container";
import MetaDetailsTooltip from "@/shared/components/display/meta-details-tooltips";
import { Link } from "@/shared/components/ui/link";

import { InlineEditRelationship } from "@/entities/nodes/object/ui/object-details/object-data-display/inline-edit-relationship";
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
  objectId: string;
  onClickMetadata?: (relationship: RelationshipSchema) => void;
}

export function ObjectRelationshipRow({
  relationshipSchema,
  relationshipData,
  permission,
  objectKind,
  objectId,
  onClickMetadata,
}: ObjectRelationshipRowProps) {
  const relationshipLabel = relationshipSchema.label ?? relationshipSchema.name;

  if (relationshipSchema.cardinality === "one") {
    return (
      <RelationshipOneRow
        relationshipSchema={relationshipSchema}
        relationshipData={relationshipData as NodeRelationshipOneWithMetadata}
        relationshipLabel={relationshipLabel}
        permission={permission}
        objectKind={objectKind}
        objectId={objectId}
        onClickMetadata={onClickMetadata}
      />
    );
  }

  return (
    <RelationshipManyRow
      relationshipSchema={relationshipSchema}
      relationshipData={relationshipData as NodeRelationshipManyWithMetadata}
      relationshipLabel={relationshipLabel}
      permission={permission}
      objectKind={objectKind}
      objectId={objectId}
      onClickMetadata={onClickMetadata}
    />
  );
}

interface RelationshipOneRowProps {
  relationshipSchema: RelationshipSchema;
  relationshipData: NodeRelationshipOneWithMetadata;
  relationshipLabel: string;
  permission: Permission;
  objectKind: string;
  objectId: string;
  onClickMetadata?: (relationship: RelationshipSchema) => void;
}

function RelationshipOneRow({
  relationshipSchema,
  relationshipData,
  relationshipLabel,
  permission,
  objectKind,
  objectId,
  onClickMetadata,
}: RelationshipOneRowProps) {
  const relatedNode = relationshipData.node;
  const relationshipProperties = relationshipData.properties;

  return (
    <ObjectDataRow
      name={relationshipLabel}
      value={
        <>
          <InlineEditRelationship
            relationshipSchema={relationshipSchema}
            relationshipData={relationshipData}
            permission={permission}
            objectKind={objectKind}
            objectId={objectId}
          >
            {relatedNode ? (
              <Link
                to={getObjectDetailsUrl(relatedNode.__typename, relatedNode.id)}
                onClick={(e) => e.stopPropagation()}
              >
                {getNodeLabel(relatedNode)}
              </Link>
            ) : (
              "-"
            )}
          </InlineEditRelationship>

          {relationshipProperties && (
            <>
              {relationshipProperties.is_protected && (
                <LockIcon className="size-3.5 text-gray-600" />
              )}

              <MetaDetailsTooltip
                updatedAt={relationshipProperties.updated_at}
                source={relationshipProperties.source}
                owner={relationshipProperties.owner}
                isProtected={relationshipProperties.is_protected}
                header={
                  onClickMetadata && (
                    <div className="flex items-center justify-between border-gray-200 border-b p-1 pt-0 pl-2">
                      <div className="font-semibold">{relationshipLabel}</div>

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
            </>
          )}
        </>
      }
    />
  );
}

interface RelationshipManyRowProps {
  relationshipSchema: RelationshipSchema;
  relationshipData: NodeRelationshipManyWithMetadata;
  relationshipLabel: string;
  permission: Permission;
  objectKind: string;
  objectId: string;
  onClickMetadata?: (relationship: RelationshipSchema) => void;
}

function RelationshipManyRow({
  relationshipSchema,
  relationshipData,
  relationshipLabel,
  permission,
  objectKind,
  objectId,
  onClickMetadata,
}: RelationshipManyRowProps) {
  const relatedNodeEdges = relationshipData.edges;

  return (
    <ObjectDataRow
      name={relationshipLabel}
      value={
        <>
          <InlineEditRelationship
            relationshipSchema={relationshipSchema}
            relationshipData={relationshipData}
            permission={permission}
            objectKind={objectKind}
            objectId={objectId}
          >
            {relatedNodeEdges.length === 0 ? (
              "-"
            ) : (
              <dl className="flex flex-col">
                {relatedNodeEdges.map((edge) => {
                  const relatedNode = edge.node;
                  const edgeProperties = edge.properties;

                  if (!relatedNode) return null;

                  return (
                    <Row key={relatedNode.id}>
                      <Link
                        to={getObjectDetailsUrl(relatedNode.__typename, relatedNode.id)}
                        onClick={(e) => e.stopPropagation()}
                      >
                        {getNodeLabel(relatedNode)}
                      </Link>

                      {edgeProperties && (
                        <>
                          <MetaDetailsTooltip
                            updatedAt={edgeProperties.updated_at}
                            source={edgeProperties.source}
                            owner={edgeProperties.owner}
                            isProtected={edgeProperties.is_protected}
                            header={
                              onClickMetadata && (
                                <div className="flex items-center justify-between border-gray-200 border-b p-1 pt-0 pl-2">
                                  <div className="font-semibold">{relationshipLabel}</div>

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
                          {edgeProperties.is_protected && (
                            <LockIcon className="size-3.5 text-gray-600" />
                          )}
                        </>
                      )}
                    </Row>
                  );
                })}
              </dl>
            )}
          </InlineEditRelationship>
        </>
      }
    />
  );
}
