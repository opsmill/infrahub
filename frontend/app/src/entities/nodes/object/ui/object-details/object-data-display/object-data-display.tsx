import { Icon } from "@iconify-icon/react";
import { Sheet } from "@infrahub/ui";
import { useState } from "react";

import { FROM_RESOURCE_POOL_SUFFIX } from "@/shared/components/form/constants";
import { sortByOrderWeight } from "@/shared/utils/common";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type {
  NodeAttributeWithMetadata,
  NodeObjectWithMetadata,
  NodeRelationshipOneWithMetadata,
} from "@/entities/nodes/object/domain/model/node";
import { getAttributesVisibleInDetailedView } from "@/entities/nodes/object/domain/rules/get-attributes-visible-in-detailed-view";
import { isRelationshipVisibleInSummary } from "@/entities/nodes/object/domain/rules/is-relationship-visible-in-summary";
import { resolveRelationshipData } from "@/entities/nodes/object/domain/rules/resolve-relationship-data";
import FieldMetadataForm from "@/entities/nodes/object/ui/metadata/field-metadata-form";
import { ObjectAttributeRow } from "@/entities/nodes/object/ui/object-details/object-data-display/object-attribute-row";
import { ObjectRelationshipRow } from "@/entities/nodes/object/ui/object-details/object-data-display/object-relationship-row";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type {
  AttributeSchema,
  ModelSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";
import { isRelationshipSchema } from "@/entities/schema/domain/rules/is-relationship-schema";

interface ObjectDataDisplayProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
  showExtra?: boolean;
  excludeRelationships?: string[];
}

export function ObjectDataDisplay({
  objectSchema,
  objectData,
  permission,
  showExtra = false,
  excludeRelationships,
}: ObjectDataDisplayProps) {
  const { currentBranch } = useCurrentBranch();
  const [showMetaEditModal, setShowMetaEditModal] = useState(false);
  const [metaEditFieldDetails, setMetaEditFieldDetails] = useState<{
    type: "attribute" | "relationship";
    attributeOrRelationshipName: any;
    label: string;
  } | null>(null);

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

  const attributes = getAttributesVisibleInDetailedView(objectSchema.attributes ?? []);
  const relationships = getRelationshipsVisibleInDataDisplay(
    objectSchema.relationships ?? [],
    excludeRelationships
  );
  const allFields = sortByOrderWeight([...attributes, ...relationships]);
  const fields = showExtra ? allFields : allFields.filter((field) => field.display !== "extra");

  return (
    <div className="divide-y divide-gray-200">
      {fields.map((field) => {
        const fieldName = field.name;
        const fieldData = objectData[fieldName];
        if (!fieldData) return null;

        const objectKind = objectSchema.kind!;

        if (isRelationshipSchema(field)) {
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

        const fromResourcePoolRelationshipName = fieldName + FROM_RESOURCE_POOL_SUFFIX;
        const fromResourcePoolRelationship = objectSchema.relationships?.find(
          (relationship) => relationship.name === fromResourcePoolRelationshipName
        );
        const poolRelData = objectData[fromResourcePoolRelationshipName] as
          | NodeRelationshipOneWithMetadata
          | undefined;

        if (fromResourcePoolRelationship && poolRelData?.node) {
          return (
            <ObjectRelationshipRow
              key={fieldName}
              relationshipSchema={{ ...fromResourcePoolRelationship, label: field.label }}
              relationshipData={poolRelData}
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

      <Sheet isOpen={showMetaEditModal} onOpenChange={setShowMetaEditModal}>
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
        <FieldMetadataForm
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
      </Sheet>
    </div>
  );
}

function getRelationshipsVisibleInDataDisplay(
  relationships: RelationshipSchema[],
  excludeRelationships?: string[]
): RelationshipSchema[] {
  return relationships.filter(
    (rel) =>
      isRelationshipVisibleInSummary(rel) &&
      (!excludeRelationships || !excludeRelationships.includes(rel.name))
  );
}
