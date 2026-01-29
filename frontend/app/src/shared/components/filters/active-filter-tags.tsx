import { TagGroup, type TagGroupProps, TagList } from "react-aria-components";

import { ScrollArea } from "@/shared/components/ui/scroll-area";
import type { Filter } from "@/shared/hooks/useFilters";
import { formatFullDate } from "@/shared/utils/date";

import { FilterResetButton } from "@/entities/nodes/object/ui/filters/filter-reset-button";
import { FilterTag } from "@/entities/nodes/object/ui/filters/filter-tag";
import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import type { AttributeKind, AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

type FieldSchema = AttributeSchema | RelationshipSchema;

export function formatAttributeFilterValue({
  kind,
  value,
}: {
  kind: AttributeKind;
  value: unknown;
}) {
  switch (kind) {
    case ATTRIBUTE_KIND.BOOLEAN:
      return String(value);
    case ATTRIBUTE_KIND.DATETIME:
      return formatFullDate(value as string | number | Date);
    default:
      return value as React.ReactNode;
  }
}

export interface ActiveFilterTagsProps extends Omit<TagGroupProps, "children"> {
  filters: Filter[];
  setFilters: (filters: Filter[]) => void;
  fieldSchemas: Record<string, FieldSchema>;
  /** Optional slot for additional custom filter tags (e.g., InternalGroupsFilterTag) */
  additionalTags?: React.ReactNode;
  /** Optional handler for custom filter removal logic */
  onCustomFilterRemove?: (filterName: string) => boolean;
}

export function ActiveFilterTags({
  filters,
  setFilters,
  fieldSchemas,
  additionalTags,
  onCustomFilterRemove,
  ...props
}: ActiveFilterTagsProps) {
  const handleRemoveFilter = (filterName: string) => {
    // Allow custom handling first
    if (onCustomFilterRemove?.(filterName)) {
      return;
    }
    setFilters(filters.filter((f) => f.name !== filterName));
  };

  const getFieldSchema = (fieldName: string): FieldSchema | undefined => {
    return fieldSchemas[fieldName];
  };

  const isRelationshipSchema = (schema: FieldSchema): schema is RelationshipSchema => {
    return "peer" in schema;
  };

  return (
    <>
      <ScrollArea scrollX>
        <TagGroup
          selectionMode="single"
          aria-label="Active filters"
          onSelectionChange={(keys) => {
            const filterName = Array.from(keys)[0]?.toString();
            if (filterName) {
              handleRemoveFilter(filterName);
            }
          }}
          onRemove={(keys) => {
            const filterName = Array.from(keys)[0]?.toString();
            if (filterName) {
              handleRemoveFilter(filterName);
            }
          }}
          {...props}
        >
          <TagList className="flex items-center gap-2 py-3">
            {additionalTags}

            {filters.map((filter) => {
              const parts = filter.name.split("__");
              if (parts.length < 2) {
                return null;
              }

              const fieldKey = parts.at(-1);
              const fieldName = parts.slice(0, -1).join("__");

              const fieldSchema = getFieldSchema(fieldName);

              if (!fieldSchema) {
                return null;
              }

              if (fieldKey === "value" || fieldKey === "values") {
                if (isRelationshipSchema(fieldSchema)) {
                  return null;
                }

                return (
                  <FilterTag
                    key={filter.name}
                    id={filter.name}
                    label={fieldSchema.label ?? fieldSchema.name}
                    value={formatAttributeFilterValue({
                      kind: fieldSchema.kind as AttributeKind,
                      value: filter.value,
                    })}
                  />
                );
              }

              if (fieldKey === "ids") {
                if (!isRelationshipSchema(fieldSchema)) {
                  return null;
                }

                if (!Array.isArray(filter.value)) {
                  return null;
                }

                const value = filter.value
                  .map((item: unknown) => {
                    if (
                      typeof item === "object" &&
                      item !== null &&
                      "display_label" in item &&
                      typeof item.display_label === "string"
                    ) {
                      return item.display_label;
                    }
                    return String(item);
                  })
                  .join(", ");

                return (
                  <FilterTag
                    key={filter.name}
                    id={filter.name}
                    label={fieldSchema.label ?? fieldSchema.name}
                    value={value}
                  />
                );
              }

              if (fieldKey === "isnull") {
                return (
                  <FilterTag
                    key={filter.name}
                    id={filter.name}
                    label={fieldSchema.label ?? fieldSchema.name}
                    value={filter.value ? "empty" : "not empty"}
                  />
                );
              }

              if (fieldKey === "before" || fieldKey === "after") {
                if (isRelationshipSchema(fieldSchema)) {
                  return null;
                }

                return (
                  <FilterTag
                    key={filter.name}
                    id={filter.name}
                    label={fieldSchema.label ?? fieldSchema.name}
                    value={`${fieldKey} ${formatFullDate(filter.value as string | number | Date)}`}
                  />
                );
              }

              return null;
            })}
          </TagList>
        </TagGroup>
      </ScrollArea>

      {filters.length > 0 && <FilterResetButton />}
    </>
  );
}
