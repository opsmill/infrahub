import { Button, Tooltip } from "@infrahub/ui";
import { LockIcon } from "lucide-react";

import { Icon } from "@/shared/components/display/icon";
import MetaDetailsTooltip from "@/shared/components/display/meta-details-tooltips";

import { ObjectAttributeValue } from "@/entities/nodes/getObjectItemDisplayValue";
import type { NodeAttributeWithMetadata } from "@/entities/nodes/object/domain/model/node";
import { ExtraFieldIndicator } from "@/entities/nodes/object/ui/object-details/object-data-display/extra-field-indicator";
import { ObjectDataRow } from "@/entities/nodes/object/ui/object-details/object-data-display/object-data-row";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { AttributeSchema } from "@/entities/schema/domain/model/schema";

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

          {attributeData.is_protected && <LockIcon className="size-3.5 text-foreground-muted" />}

          <MetaDetailsTooltip
            updatedAt={attributeData.updated_at}
            source={attributeData.source}
            owner={attributeData.owner}
            triggerClassName="opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
            isProtected={attributeData.is_protected}
            header={
              !attributeSchema.read_only && (
                <div className="flex items-center justify-between border-border-strong border-b p-1 pl-2">
                  <div className="font-semibold text-sm">{attributeLabel}</div>
                  {onClickMetadata && (
                    <Tooltip message={permission.update.message}>
                      <Button
                        isDisabledAndFocusable={!permission.update.isAllowed}
                        onPress={() => {
                          onClickMetadata(attributeSchema);
                        }}
                        variant="ghost"
                        size="xs"
                        shape="circle"
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

          {attributeSchema.display === "extra" && <ExtraFieldIndicator className="ml-auto" />}
        </>
      }
    />
  );
}
