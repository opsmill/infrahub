import { Icon } from "@iconify-icon/react";

import { Row } from "@/shared/components/container";
import type { Filter } from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";

import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";
import { FieldSchemaIcon } from "@/entities/schema/ui/field-schema-icon";

interface FilterMenuItemProps {
  schema: AttributeSchema | RelationshipSchema;
  filters: Filter[];
  onHover: (schema: AttributeSchema | RelationshipSchema) => void;
  isHovered: boolean;
}

export function FilterMenuItem({ schema, filters, onHover, isHovered }: FilterMenuItemProps) {
  const isActive = filters.some((f) => f.name.startsWith(schema.name));

  return (
    <Row
      className={classNames(
        "cursor-pointer gap-2 rounded px-2 py-1.5 text-sm",
        isHovered ? "bg-gray-100" : "hover:bg-gray-50",
        isActive && "font-medium"
      )}
      onPointerEnter={() => onHover(schema)}
    >
      <FieldSchemaIcon fieldSchema={schema} />
      <span className="truncate">{schema.label ?? schema.name}</span>
      {isActive && (
        <Icon icon="mdi:check" className="ml-auto shrink-0 text-base text-custom-blue-700" />
      )}
    </Row>
  );
}
