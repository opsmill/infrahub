import { Icon } from "@iconify-icon/react";
import { LockIcon } from "lucide-react";

import { Button } from "@/shared/components/aria/button";
import { Tooltip } from "@/shared/components/aria/tooltip";
import MetaDetailsTooltip from "@/shared/components/display/meta-details-tooltips";

import { ObjectAttributeValue } from "@/entities/nodes/getObjectItemDisplayValue";
import { ExtraFieldIndicator } from "@/entities/nodes/object/ui/object-details/object-data-display/extra-field-indicator";
import { ObjectDataRow } from "@/entities/nodes/object/ui/object-details/object-data-display/object-data-row";
import type { NodeAttributeWithMetadata } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { AttributeSchema } from "@/entities/schema/types";

interface ObjectAttributeRowProps {
  attributeSchema: AttributeSchema;
  attributeData: NodeAttributeWithMetadata;
  permission: Permission;
  objectKind: string;
  onClickMetadata?: (attribute: AttributeSchema) => void;
}

export function ObjectAttributeRow({
  attributeSchema,
  attributeData,
  objectKind,
  onClickMetadata,
  permission,
}: ObjectAttributeRowProps) {
  const attributeLabel = attributeSchema.label ?? attributeSchema.name;

  return (
    <ObjectDataRow
      fieldSchema={attributeSchema}
      objectKind={objectKind}
      value={
        <>
          <ObjectAttributeValue attributeSchema={attributeSchema} attributeData={attributeData} />

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
                    <Tooltip message={permission.update.message}>
                      <Button
                        isDisabledAndFocusable={!permission.update.isAllowed}
                        onPress={() => {
                          onClickMetadata(attributeSchema);
                        }}
                        variant="ghost"
                        size="icon"
                        data-testid="edit-metadata-button"
                      >
                        <Icon icon="mdi:pencil" className="text-custom-blue-500" />
                      </Button>
                    </Tooltip>
                  )}
                </div>
              )
            }
          />

          {attributeData.is_protected && <LockIcon className="size-3.5 text-gray-600" />}

          {attributeSchema.display === "extra" && <ExtraFieldIndicator className="ml-auto" />}
        </>
      }
    />
  );
}
