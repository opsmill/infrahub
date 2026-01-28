import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { useState } from "react";

import SlideOver from "@/shared/components/display/slide-over";
import { sortByOrderWeight } from "@/shared/utils/common";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { ObjectAttributeRow } from "@/entities/nodes/object/ui/object-details/object-data-display/object-attribute-row";
import { ObjectRelationshipRow } from "@/entities/nodes/object/ui/object-details/object-data-display/object-relationship-row";
import { getAttributesVisibleInDetailedView } from "@/entities/nodes/object/utils/get-attributes-visible-in-detailed-view";
import { getRelationshipsVisibleInDetailedView } from "@/entities/nodes/object/utils/get-relationships-visible-in-detailed-view";
import ObjectItemMetaEdit from "@/entities/nodes/object-item-meta-edit/object-item-meta-edit";
import { metaEditFieldDetailsState } from "@/entities/nodes/stores/showMetaEdit.atom";
import type {
  NodeAttributeWithMetadata,
  NodeObjectWithMetadata,
  NodeRelationshipWithMetadata,
} from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";

const DEFAULT_EXCLUDED_RELATIONSHIPS = ["member_of_groups"];
const DEFAULT_EXCLUDED_RELATIONSHIP_KINDS = ["Profile"];

interface ObjectDataDisplayProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
  /** Attribute names to exclude from display */
  excludeAttributes?: string[];
  /** Relationship names to exclude from display */
  excludeRelationships?: string[];
  /** Relationship kinds to exclude from display */
  excludeRelationshipKinds?: string[];
}

export function ObjectDataDisplay({
  objectSchema,
  objectData,
  permission,
  excludeAttributes = [],
  excludeRelationships = DEFAULT_EXCLUDED_RELATIONSHIPS,
  excludeRelationshipKinds = DEFAULT_EXCLUDED_RELATIONSHIP_KINDS,
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

  const attributes = getAttributesVisibleInDetailedView(objectSchema.attributes ?? []).filter(
    (attr) => !excludeAttributes.includes(attr.name)
  );
  const relationships = getRelationshipsVisibleInDetailedView(
    objectSchema.relationships ?? []
  ).filter(
    (rel) =>
      !excludeRelationships.includes(rel.name) && !excludeRelationshipKinds.includes(rel.kind)
  );
  const fields = sortByOrderWeight([...attributes, ...relationships]);

  return (
    <div className="divide-y divide-gray-200">
      {fields.map((field) => {
        const fieldName = field.name;
        const fieldData = objectData[fieldName];
        if (!fieldData) return null;

        const objectKind = objectSchema.kind!;

        if ("peer" in field) {
          return (
            <ObjectRelationshipRow
              key={fieldName}
              relationshipSchema={field}
              relationshipData={fieldData as NodeRelationshipWithMetadata}
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
