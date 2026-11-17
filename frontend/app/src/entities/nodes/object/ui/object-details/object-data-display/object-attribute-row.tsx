import { LockIcon } from "lucide-react";

import { ObjectAttributeValue } from "@/entities/nodes/getObjectItemDisplayValue";
import type { NodeAttributeWithMetadata } from "@/entities/nodes/object/domain/model/node";
import { EditMetadataButton } from "@/entities/nodes/object/ui/metadata/edit-metadata-button";
import {
  FieldMetadataPopover,
  METADATA_HOVER_AREA,
} from "@/entities/nodes/object/ui/metadata/field-metadata-popover";
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
  const canEditMetadata = !attributeSchema.read_only;

  return (
    <ObjectDataRow
      className={METADATA_HOVER_AREA}
      fieldSchema={attributeSchema}
      objectKind={objectKind}
      value={
        <>
          <ObjectAttributeValue attributeSchema={attributeSchema} attributeData={attributeData} />

          {attributeData.is_protected && <LockIcon className="size-3.5 text-foreground-muted" />}

          <FieldMetadataPopover
            metadata={attributeData}
            revealOnHover
            title={canEditMetadata ? attributeLabel : undefined}
            action={
              canEditMetadata && onClickMetadata ? (
                <EditMetadataButton
                  onPress={() => onClickMetadata(attributeSchema)}
                  permission={permission.update}
                />
              ) : undefined
            }
          />

          {attributeSchema.display === "extra" && <ExtraFieldIndicator className="ml-auto" />}
        </>
      }
    />
  );
}
