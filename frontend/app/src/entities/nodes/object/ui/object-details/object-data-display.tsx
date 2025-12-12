import { LockClosedIcon } from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";

import { ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import MetaDetailsTooltip from "@/shared/components/display/meta-details-tooltips";
import { sortByOrderWeight } from "@/shared/utils/common";

import { ObjectAttributeValue } from "@/entities/nodes/getObjectItemDisplayValue";
import { getAttributesVisibleInDetailedView } from "@/entities/nodes/object/utils/get-attributes-visible-in-detailed-view";
import { getRelationshipsVisibleInDetailedView } from "@/entities/nodes/object/utils/get-relationships-visible-in-detailed-view";
import { ObjectAttributeRow } from "@/entities/nodes/object-item-details/object-attribute-row";
import RelationshipDetails from "@/entities/nodes/object-item-details/relationship-details-paginated";
import type {
  NodeAttributeWithMetadata,
  NodeObjectWithMetadata,
  NodeRelationshipManyWithMetadata,
  NodeRelationshipOneWithMetadata,
} from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";

interface ObjectDataDisplayProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
  onClickMetadata?: (attribute: AttributeSchema) => void;
}

export function ObjectDataDisplay({
  objectSchema,
  objectData,
  permission,
  onClickMetadata,
}: ObjectDataDisplayProps) {
  const attributes = getAttributesVisibleInDetailedView(objectSchema.attributes ?? []);
  const relationships = getRelationshipsVisibleInDetailedView(objectSchema.relationships ?? []);
  const fields = sortByOrderWeight([...attributes, ...relationships]);

  return (
    <div className="divide-y divide-gray-200">
      {fields.map((field) => {
        const fieldName = field.name;
        const fieldData = objectData[fieldName];
        if (!fieldData) return null;

        if ("peer" in field) {
          return (
            <NodeRelationshipRow
              key={fieldName}
              objectSchema={objectSchema}
              objectData={objectData}
              relationship={field}
            />
          );
        }

        return (
          <NodeAttributeRow
            key={fieldName}
            attribute={field}
            attributeData={fieldData as NodeAttributeWithMetadata}
            permission={permission}
            onClickMetadata={onClickMetadata}
          />
        );
      })}
    </div>
  );
}

interface NodeAttributeRowProps {
  attribute: AttributeSchema;
  attributeData: NodeAttributeWithMetadata;
  permission: Permission;
  onClickMetadata?: (attribute: AttributeSchema) => void;
}

function NodeAttributeRow({
  attribute,
  attributeData,
  onClickMetadata,
  permission,
}: NodeAttributeRowProps) {
  return (
    <ObjectAttributeRow
      key={attribute.name}
      name={attribute.label ?? attribute.name}
      value={
        <>
          <ObjectAttributeValue attributeSchema={attribute} attributeData={attributeData} />

          <MetaDetailsTooltip
            updatedAt={attributeData.updated_at}
            source={attributeData.source}
            owner={attributeData.owner}
            isProtected={attributeData.is_protected}
            header={
              !attribute.read_only && (
                <div className="flex items-center justify-between border-gray-200 border-b p-1 pt-0 pl-2">
                  <div className="font-semibold">{attribute.label}</div>
                  {onClickMetadata && (
                    <ButtonWithTooltip
                      disabled={!permission.update.isAllowed}
                      tooltipEnabled={!permission.update.isAllowed}
                      tooltipContent={permission.update.message}
                      onClick={() => {
                        onClickMetadata(attribute);
                      }}
                      variant="ghost"
                      size="icon"
                      data-testid="edit-metadata-button"
                      data-cy="metadata-edit-button"
                    >
                      <Icon icon="mdi:pencil" className="text-custom-blue-500" />
                    </ButtonWithTooltip>
                  )}
                </div>
              )
            }
          />

          {attributeData.is_protected && <LockClosedIcon className="size-4" />}
        </>
      }
    />
  );
}

interface NodeRelationshipRowProps {
  relationship: RelationshipSchema;
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
}

function NodeRelationshipRow({ relationship, objectSchema, objectData }: NodeRelationshipRowProps) {
  const relationshipSchema = objectSchema.relationships?.find(
    (relation) => relation?.name === relationship?.name
  );

  const relationshipData =
    relationship.cardinality === "one"
      ? (objectData[relationship.name] as NodeRelationshipOneWithMetadata | undefined)
      : (objectData[relationship.name] as NodeRelationshipManyWithMetadata | undefined)?.edges;

  return (
    <RelationshipDetails
      parentNode={objectData}
      mode="DESCRIPTION-LIST"
      parentSchema={objectSchema}
      key={relationship.name}
      relationshipsData={relationshipData}
      relationshipSchema={relationshipSchema}
    />
  );
}
