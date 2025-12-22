import { Icon } from "@iconify-icon/react";
import { LockIcon } from "lucide-react";

import { ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import MetaDetailsTooltip from "@/shared/components/display/meta-details-tooltips";

import { ObjectAttributeValue } from "@/entities/nodes/getObjectItemDisplayValue";
import { InlineEdit } from "@/entities/nodes/object/ui/object-details/object-data-display/inline-edit";
import { ObjectDataRow } from "@/entities/nodes/object/ui/object-details/object-data-display/object-data-row";
import type { NodeAttributeWithMetadata } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { AttributeSchema } from "@/entities/schema/types";

interface ObjectAttributeRowProps {
  attributeSchema: AttributeSchema;
  attributeData: NodeAttributeWithMetadata;
  permission: Permission;
  objectKind: string;
  objectId: string;
  onClickMetadata?: (attribute: AttributeSchema) => void;
}

export function ObjectAttributeRow({
  attributeSchema,
  attributeData,
  onClickMetadata,
  permission,
  objectKind,
  objectId,
}: ObjectAttributeRowProps) {
  const attributeLabel = attributeSchema.label ?? attributeSchema.name;

  return (
    <ObjectDataRow
      name={attributeLabel}
      value={
        <>
          <InlineEdit
            fieldSchema={attributeSchema}
            fieldData={attributeData}
            permission={permission}
            objectKind={objectKind}
            objectId={objectId}
          >
            <ObjectAttributeValue attributeSchema={attributeSchema} attributeData={attributeData} />
          </InlineEdit>

          {attributeData.is_protected && <LockIcon className="size-3.5 shrink-0 text-gray-600" />}

          <MetaDetailsTooltip
            updatedAt={attributeData.updated_at}
            source={attributeData.source}
            owner={attributeData.owner}
            isProtected={attributeData.is_protected}
            header={
              !attributeSchema.read_only && (
                <div className="flex items-center justify-between border-gray-200 border-b p-1 pt-0 pl-2">
                  <div className="font-semibold">{attributeLabel}</div>
                  {onClickMetadata && (
                    <ButtonWithTooltip
                      disabled={!permission.update.isAllowed}
                      tooltipEnabled={!permission.update.isAllowed}
                      tooltipContent={permission.update.message}
                      onClick={() => {
                        onClickMetadata(attributeSchema);
                      }}
                      variant="ghost"
                      size="icon"
                      data-testid="edit-metadata-button"
                    >
                      <Icon icon="mdi:pencil" className="text-custom-blue-500" />
                    </ButtonWithTooltip>
                  )}
                </div>
              )
            }
          />
        </>
      }
    />
  );
}
