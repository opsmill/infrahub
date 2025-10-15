import { LockClosedIcon } from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";

import { ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import MetaDetailsTooltip from "@/shared/components/display/meta-details-tooltips";

import { ObjectAttributeValue } from "@/entities/nodes/getObjectItemDisplayValue";
import { ObjectAttributeRow } from "@/entities/nodes/object-item-details/object-attribute-row";
import RelationshipDetails from "@/entities/nodes/object-item-details/relationship-details-paginated";
import type { Permission } from "@/entities/permission/types";
import type { AttributeSchema, ModelSchema } from "@/entities/schema/types";

import {
  getObjectAttributes,
  getObjectRelationships,
} from "../../object-items/getSchemaObjectColumns";
import type { NodeObject } from "../../types";

type ObjectDetailsContentProps = {
  schema: ModelSchema;
  objectDetailsData: NodeObject;
  permission: Permission;
  onClickMetadata?: (attribute: AttributeSchema) => void;
};

export function ObjectDetailsContent({
  schema,
  objectDetailsData,
  permission,
  onClickMetadata,
}: ObjectDetailsContentProps) {
  const attributes = getObjectAttributes({ schema });
  const relationships = getObjectRelationships({ schema });

  return (
    <div className="divide-y divide-gray-200">
      {attributes.map((attribute) => {
        if (!objectDetailsData[attribute.name]) {
          return null;
        }

        return (
          <ObjectAttributeRow
            key={attribute.name}
            name={attribute.label as string}
            value={
              <>
                <ObjectAttributeValue
                  attributeSchema={attribute}
                  attributeValue={objectDetailsData[attribute.name]}
                />

                {objectDetailsData[attribute.name] && (
                  <MetaDetailsTooltip
                    updatedAt={objectDetailsData[attribute.name]?.updated_at}
                    source={objectDetailsData[attribute.name]?.source}
                    owner={objectDetailsData[attribute.name]?.owner}
                    isFromProfile={objectDetailsData[attribute.name]?.is_from_profile}
                    isProtected={objectDetailsData[attribute.name]?.is_protected}
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
                )}

                {objectDetailsData[attribute.name]?.is_protected && (
                  <LockClosedIcon className="h-4 w-4" />
                )}
              </>
            }
          />
        );
      })}

      {relationships?.map((relationship: any) => {
        const relationshipSchema = schema?.relationships?.find(
          (relation) => relation?.name === relationship?.name
        );

        const relationshipData = relationship?.paginated
          ? objectDetailsData[relationship.name]?.edges
          : objectDetailsData[relationship.name];

        return (
          <RelationshipDetails
            parentNode={objectDetailsData}
            mode="DESCRIPTION-LIST"
            parentSchema={schema}
            key={relationship.name}
            relationshipsData={relationshipData}
            relationshipSchema={relationshipSchema}
          />
        );
      })}
    </div>
  );
}
