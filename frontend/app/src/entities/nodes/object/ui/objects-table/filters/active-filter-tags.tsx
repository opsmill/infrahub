import { AttributeType } from "@/entities/nodes/getObjectItemDisplayValue";
import { FilterTag } from "@/entities/nodes/object/ui/objects-table/filters/filter-tag";
import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import { AttributeKind } from "@/entities/schema/types";
import useFilters from "@/shared/hooks/useFilters";
import { formatFullDate } from "@/shared/utils/date";
import { Selection, TagGroup, TagList } from "react-aria-components";

export function formatAttributeFilterValue({
  kind,
  value,
}: { kind: AttributeKind; value: AttributeType["value"] }) {
  switch (kind) {
    case ATTRIBUTE_KIND.BOOLEAN:
      return value.toString();
    case ATTRIBUTE_KIND.DATETIME:
      return formatFullDate(value);
    default:
      return value;
  }
}

export interface ObjectsFilterTagsProps {
  schema: IModelSchema;
}

export function ActiveFilterTags({ schema }: ObjectsFilterTagsProps) {
  const [filters, setFilters] = useFilters();

  const handleRemoveFilter = (keys: Selection) => {
    const filterName = Array.from(keys)[0]?.toString();
    if (filterName) {
      setFilters(filters.filter((f) => f.name !== filterName));
    }
  };

  return (
    <TagGroup
      selectionMode="single"
      aria-label="Active filters"
      onSelectionChange={handleRemoveFilter}
      onRemove={handleRemoveFilter}
    >
      <TagList className="flex items-center gap-2 py-3">
        {filters.map((filter) => {
          const [fieldName, fieldKey] = filter.name.split("__");

          if (!fieldName || !fieldKey) {
            return null;
          }

          if (fieldKey === "value" || fieldKey === "values") {
            const attributeSchema = schema.attributes?.find(({ name }) => name === fieldName);
            if (!attributeSchema) {
              return null;
            }

            return (
              <FilterTag
                key={filter.name}
                id={filter.name}
                label={attributeSchema.label ?? attributeSchema.name}
                value={formatAttributeFilterValue({
                  kind: attributeSchema.kind as AttributeKind,
                  value: filter.value,
                })}
              />
            );
          }

          if (fieldKey === "ids") {
            const relationshipSchema = schema.relationships?.find(({ name }) => name === fieldName);
            if (!relationshipSchema) {
              return null;
            }

            const value = filter.value
              .map(({ display_label }: { display_label: string }) => display_label)
              .join(", ");

            return (
              <FilterTag
                key={filter.name}
                id={filter.name}
                label={relationshipSchema.label ?? relationshipSchema.name}
                value={value}
              />
            );
          }

          return null;
        })}
      </TagList>
    </TagGroup>
  );
}
