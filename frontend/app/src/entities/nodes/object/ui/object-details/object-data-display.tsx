import { LockClosedIcon } from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";

import { ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import MetaDetailsTooltip from "@/shared/components/display/meta-details-tooltips";
import SlideOver from "@/shared/components/display/slide-over";
import { sortByOrderWeight } from "@/shared/utils/common";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { ObjectAttributeValue } from "@/entities/nodes/getObjectItemDisplayValue";
import { getAttributesVisibleInDetailedView } from "@/entities/nodes/object/utils/get-attributes-visible-in-detailed-view";
import { getRelationshipsVisibleInDetailedView } from "@/entities/nodes/object/utils/get-relationships-visible-in-detailed-view";
import { ObjectAttributeRow } from "@/entities/nodes/object-item-details/object-attribute-row";
import RelationshipDetails from "@/entities/nodes/object-item-details/relationship-details-paginated";
import ObjectItemMetaEdit from "@/entities/nodes/object-item-meta-edit/object-item-meta-edit";
import { showMetaEditState } from "@/entities/nodes/stores/metaEditFieldDetails.atom";
import { metaEditFieldDetailsState } from "@/entities/nodes/stores/showMetaEdit.atom";
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
}

export function ObjectDataDisplay({
  objectSchema,
  objectData,
  permission,
}: ObjectDataDisplayProps) {
  const { currentBranch } = useCurrentBranch();
  const [showMetaEditModal, setShowMetaEditModal] = useAtom(showMetaEditState);
  const [metaEditFieldDetails, setMetaEditFieldDetails] = useAtom(metaEditFieldDetailsState);

  const onClickMetadata = (attribute: AttributeSchema) => {
    setMetaEditFieldDetails({
      type: "attribute",
      attributeOrRelationshipName: attribute.name,
      label: attribute.label || attribute.name,
    });

    setShowMetaEditModal(true);
  };

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

      <SlideOver
        title={
          <div className="space-y-2">
            <div className="flex w-full items-center">
              <span className="mr-3 font-semibold text-lg">{metaEditFieldDetails?.label}</span>
              <div className="flex-1"></div>
              <div className="flex items-center">
                <Icon icon={"mdi:layers-triple"} />
                <div className="ml-1.5 pb-1">{currentBranch.name}</div>
              </div>
            </div>
            <div className="text-gray-500">Metadata</div>
          </div>
        }
        open={showMetaEditModal}
        setOpen={setShowMetaEditModal}
      >
        <ObjectItemMetaEdit
          onCancel={() => setShowMetaEditModal(false)}
          onSuccess={() => setShowMetaEditModal(false)}
          attributeOrRelationshipToEdit={
            objectData[metaEditFieldDetails?.attributeOrRelationshipName]?.properties ||
            objectData[metaEditFieldDetails?.attributeOrRelationshipName]
          }
          schema={objectSchema}
          attributeOrRelationshipName={metaEditFieldDetails?.attributeOrRelationshipName}
          type={metaEditFieldDetails?.type!}
          row={objectData}
        />
      </SlideOver>
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
  const attributeLabel = attribute.label ?? attribute.name;
  return (
    <ObjectAttributeRow
      name={attributeLabel}
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
                  <div className="font-semibold">{attributeLabel}</div>
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
      relationshipsData={relationshipData}
      relationshipSchema={relationshipSchema}
    />
  );
}
