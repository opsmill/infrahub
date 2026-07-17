import type { Sort, SortDirection } from "@/entities/nodes/sort/domain/model/sort";
import { buildAttributeSortField } from "@/entities/nodes/sort/domain/rules/sort-field";
import { SortableFieldMenuItem } from "@/entities/nodes/sort/ui/sortable-field-menu-item";
import type { AttributeSchema } from "@/entities/schema/domain/model/schema";
import { FieldSchemaIcon } from "@/entities/schema/ui/field-schema-icon";

export interface SortableAttributeMenuItemProps {
  attribute: AttributeSchema;
  /** Direction of the active sort when this attribute drives it. */
  activeDirection?: SortDirection;
  onSelect: (sort: Sort) => void;
}

export function SortableAttributeMenuItem({
  attribute,
  activeDirection,
  onSelect,
}: SortableAttributeMenuItemProps) {
  return (
    <SortableFieldMenuItem
      field={buildAttributeSortField(attribute.name)}
      icon={<FieldSchemaIcon fieldSchema={attribute} />}
      label={attribute.label ?? attribute.name}
      activeDirection={activeDirection}
      onSelect={onSelect}
    />
  );
}
