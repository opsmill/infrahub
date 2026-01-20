import { Icon } from "@iconify-icon/react";
import type React from "react";
import { Button, DialogTrigger } from "react-aria-components";

import { classNames } from "@/shared/utils/common";

import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";
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

  const fieldName = fieldSchema.label ?? fieldSchema.name;
  const isRelationship = "peer" in fieldSchema;
  const defaultTab = isRelationship ? "relationships" : "attributes";

  return (
    <div className={classNames("grid grid-cols-[200px_auto] gap-4 px-4 py-2 text-xs", className)}>
      <dt className="flex h-8 items-center font-medium text-gray-500">
        {schema ? (
          <DialogTrigger>
            <Button
              className="group flex cursor-pointer items-center outline-hidden hover:text-custom-blue-700"
              excludeFromTabOrder
            >
              {fieldName}
              <Icon icon="mdi:code-json" className="ml-1 hidden group-hover:inline-block" />
            </Button>

            <SchemaViewerModal
              schema={schema}
              defaultTab={defaultTab}
              targetField={fieldSchema.name}
            />
          </DialogTrigger>
        ) : (
          fieldName
        )}
      </dt>
      <dd className="flex items-center gap-2">{value}</dd>
    </div>
  );
}
