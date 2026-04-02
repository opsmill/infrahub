import { useState } from "react";
import { TagGroup, type TagGroupProps, TagList } from "react-aria-components";

import { Popover, PopoverAnchor, PopoverContent } from "@/shared/components/ui/popover";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import type { Filter } from "@/shared/hooks/useFilters";
import { formatFullDate } from "@/shared/utils/date";

import { FilterFormDispatch } from "@/entities/nodes/object/ui/filters/filter-form-dispatch";
import { FilterResetButton } from "@/entities/nodes/object/ui/filters/filter-reset-button";
import { FilterTag } from "@/entities/nodes/object/ui/filters/filter-tag";
import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import type { AttributeKind, AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

type FieldSchema = AttributeSchema | RelationshipSchema;

const EMPTY_DISPLAY = { label: null, condition: "", value: "" } as const;

function isRelationshipSchema(schema: FieldSchema): schema is RelationshipSchema {
  return "peer" in schema;
}

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
    if (onCustomFilterRemove?.(filterName)) {
      return;
    }
    setFilters(filters.filter((f) => f.name !== filterName));
  };

  if (filters.length === 0 && !additionalTags) {
    return null;
  }

  return (
    <ScrollArea scrollX>
      <div className="flex items-center gap-2">
        <TagGroup
          aria-label="Active filters"
          onRemove={(keys) => {
            const filterName = Array.from(keys)[0]?.toString();
            if (filterName) {
              handleRemoveFilter(filterName);
            }
          }}
          {...props}
        >
          <TagList className="flex items-center gap-2">
            {additionalTags}

            {filters.map((filter) => {
              const parts = filter.name.split("__");
              if (parts.length < 2) {
                return null;
              }

              const fieldKey = parts.at(-1);
              const fieldName = parts.slice(0, -1).join("__");
              const fieldSchema = fieldSchemas[fieldName];

              if (!fieldSchema) {
                return null;
              }

              return (
                <EditableFilterTag
                  key={filter.name}
                  filter={filter}
                  fieldKey={fieldKey}
                  fieldSchema={fieldSchema}
                />
              );
            })}
          </TagList>
        </TagGroup>

        {filters.length > 0 && <FilterResetButton />}
      </div>
    </ScrollArea>
  );
}

interface EditableFilterTagProps {
  filter: Filter;
  fieldKey: string | undefined;
  fieldSchema: FieldSchema;
}

function EditableFilterTag({ filter, fieldKey, fieldSchema }: EditableFilterTagProps) {
  const isRelationship = isRelationshipSchema(fieldSchema);
  const [editOpen, setEditOpen] = useState(false);

  const { label, condition, value } = getFilterTagDisplay({
    filter,
    fieldKey,
    fieldSchema,
    isRelationship,
  });

  if (!label) return null;

  return (
    <Popover open={editOpen} onOpenChange={setEditOpen}>
      <PopoverAnchor asChild>
        <FilterTag
          id={filter.name}
          label={label}
          condition={condition}
          value={value}
          onEdit={() => setEditOpen(true)}
        />
      </PopoverAnchor>

      <PopoverContent align="start" className="p-0" sideOffset={4}>
        <FilterFormDispatch fieldSchema={fieldSchema} onSuccess={() => setEditOpen(false)} />
      </PopoverContent>
    </Popover>
  );
}

function getFilterTagDisplay({
  filter,
  fieldKey,
  fieldSchema,
  isRelationship,
}: {
  filter: Filter;
  fieldKey: string | undefined;
  fieldSchema: FieldSchema;
  isRelationship: boolean;
}): { label: React.ReactNode; condition: string; value: React.ReactNode } {
  const name = fieldSchema.label ?? fieldSchema.name;

  if (fieldKey === "value" || fieldKey === "values") {
    if (isRelationship) return EMPTY_DISPLAY;

    return {
      label: name,
      condition: "contains",
      value: formatAttributeFilterValue({
        kind: (fieldSchema as AttributeSchema).kind as AttributeKind,
        value: filter.value,
      }),
    };
  }

  if (fieldKey === "ids") {
    if (!isRelationship) return EMPTY_DISPLAY;
    if (!Array.isArray(filter.value)) return EMPTY_DISPLAY;

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

    return { label: name, condition: "is any of", value };
  }

  if (fieldKey === "isnull") {
    return {
      label: name,
      condition: filter.value ? "is empty" : "is not empty",
      value: "",
    };
  }

  if (fieldKey === "before" || fieldKey === "after") {
    if (isRelationship) return EMPTY_DISPLAY;

    return {
      label: name,
      condition: fieldKey,
      value: formatFullDate(filter.value as string | number | Date),
    };
  }

  return EMPTY_DISPLAY;
}
