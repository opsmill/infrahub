import type React from "react";
import { Button, DialogTrigger } from "react-aria-components";

import { Row } from "@/shared/components/container";
import { Icon } from "@/shared/components/display/icon";
import { classNames } from "@/shared/utils/common";

import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";
import { getRelationshipLabel } from "@/entities/schema/domain/rules/get-relationship-label";
import { isRelationshipSchema } from "@/entities/schema/domain/rules/is-relationship-schema";
import { FieldSchemaIcon } from "@/entities/schema/ui/field-schema-icon";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { SchemaViewerModal } from "@/entities/schema/ui/schema-viewer-modal";

interface ObjectDataRowProps {
  fieldSchema: AttributeSchema | RelationshipSchema;
  value: React.ReactNode;
  objectKind: string;
  className?: string;
}

export function ObjectDataRow({ value, className, objectKind, fieldSchema }: ObjectDataRowProps) {
  const { schema } = useSchema(objectKind);
  const isRelationship = isRelationshipSchema(fieldSchema);
  const { schema: peerSchema } = useSchema(isRelationship ? fieldSchema.peer : undefined);

  const fieldName = isRelationship
    ? getRelationshipLabel(fieldSchema, peerSchema)
    : (fieldSchema.label ?? fieldSchema.name);
  const defaultTab = isRelationship ? "relationships" : "attributes";

  return (
    <div className={classNames("group grid grid-cols-[200px_auto] gap-4 px-3 py-2 text-sm", className)}>
      <dt className="flex h-8 items-center font-medium text-foreground-muted">
        {schema ? (
          <DialogTrigger>
            <Button className="group flex cursor-pointer items-center gap-1.5 data-hovered:text-custom-blue-700">
              <FieldSchemaIcon fieldSchema={fieldSchema} />
              {fieldName}
              <Icon icon="mdi:code-json" className="hidden group-hover:inline-block" />
            </Button>

            <SchemaViewerModal
              schema={schema}
              defaultTab={defaultTab}
              targetField={fieldSchema.name}
            />
          </DialogTrigger>
        ) : (
          <Row className="gap-1.5">
            <FieldSchemaIcon fieldSchema={fieldSchema} />
            {fieldName}
          </Row>
        )}
      </dt>
      <dd className="flex items-center gap-2 text-foreground">{value}</dd>
    </div>
  );
}
