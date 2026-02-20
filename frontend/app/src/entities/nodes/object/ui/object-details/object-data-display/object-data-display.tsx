import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { useState } from "react";

import SlideOver from "@/shared/components/display/slide-over";
import { FILE_OBJECT_KIND } from "@/shared/config/constants";
import { sortByOrderWeight } from "@/shared/utils/common";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { ObjectAttributeRow } from "@/entities/nodes/object/ui/object-details/object-data-display/object-attribute-row";
import { ObjectRelationshipRow } from "@/entities/nodes/object/ui/object-details/object-data-display/object-relationship-row";
import { getAttributesVisibleInDetailedView } from "@/entities/nodes/object/utils/get-attributes-visible-in-detailed-view";
import { getAttributesVisibleInFileObject } from "@/entities/nodes/object/utils/get-attributes-visible-in-file-object";
import { isRelationshipVisibleInDetailedView } from "@/entities/nodes/object/utils/get-relationships-visible-in-detailed-view";
import { isFromResourcePoolRelationship } from "@/entities/nodes/object/utils/is-from-resource-pool-relationship";
import { resolveRelationshipData } from "@/entities/nodes/object/utils/resolve-relationship-data";
import ObjectItemMetaEdit from "@/entities/nodes/object-item-meta-edit/object-item-meta-edit";
import { metaEditFieldDetailsState } from "@/entities/nodes/stores/showMetaEdit.atom";
import type { NodeAttributeWithMetadata, NodeObjectWithMetadata } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

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
  const [showMetaEditModal, setShowMetaEditModal] = useState(false);
  const [metaEditFieldDetails, setMetaEditFieldDetails] = useAtom(metaEditFieldDetailsState);

  const onClickAttributeMetadata = (attribute: AttributeSchema) => {
    setMetaEditFieldDetails({
      type: "attribute",
      attributeOrRelationshipName: attribute.name,
      label: attribute.label || attribute.name,
    });

    setShowMetaEditModal(true);
  };

  const onClickRelationshipMetadata = (relationship: RelationshipSchema) => {
    setMetaEditFieldDetails({
      type: "relationship",
      attributeOrRelationshipName: relationship.name,
      label: relationship.label || relationship.name,
    });

    setShowMetaEditModal(true);
  };

  const attributes = isOfKind(FILE_OBJECT_KIND, objectSchema)
    ? getAttributesVisibleInFileObject(objectSchema.attributes ?? [])
    : getAttributesVisibleInDetailedView(objectSchema.attributes ?? []);
  const relationships = getRelationshipsVisibleInDataDisplay(objectSchema.relationships ?? []);
  const fields = sortByOrderWeight([...attributes, ...relationships]);

  return (
    <div className="divide-y divide-gray-200">
      {fields.map((field) => {
        const fieldName = field.name;
        const fieldData = objectData[fieldName];
        if (!fieldData) return null;

        const objectKind = objectSchema.kind!;

        if ("peer" in field) {
          const relationshipData = resolveRelationshipData({
            relationshipName: fieldName,
            objectSchema,
            objectData,
          });

          return (
            <ObjectRelationshipRow
              key={fieldName}
              relationshipSchema={field}
              relationshipData={relationshipData}
              objectKind={objectKind}
              permission={permission}
              onClickMetadata={onClickRelationshipMetadata}
            />
          );
        }

        return (
          <ObjectAttributeRow
            key={fieldName}
            attributeSchema={field}
            attributeData={fieldData as NodeAttributeWithMetadata}
            objectKind={objectKind}
            permission={permission}
            onClickMetadata={onClickAttributeMetadata}
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

function getRelationshipsVisibleInDataDisplay(
  relationships: RelationshipSchema[]
): RelationshipSchema[] {
  return relationships.filter(
    (rel) =>
      isRelationshipVisibleInDetailedView(rel) &&
      rel.name !== "member_of_groups" &&
      !isFromResourcePoolRelationship(rel.name) &&
      rel.kind !== "Profile"
  );
}
