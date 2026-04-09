import { useRef, useState } from "react";
import { type Selection, TagGroup, type TagGroupProps, TagList } from "react-aria-components";

import { Popover } from "@/shared/components/aria/popover";
import { Row } from "@/shared/components/container";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import type { Filter } from "@/shared/hooks/useFilters";
import { formatFullDate } from "@/shared/utils/date";

import {
  AVAILABLE_IP_FILTER_NAME,
  HIDE_AVAILABLE_IP,
  HIDE_AVAILABLE_IP_FILTER,
  SHOW_AVAILABLE_IP,
} from "@/entities/ipam/constants";
import type { FilterDefinition } from "@/entities/nodes/object/domain/filter-definition";
import { getFilterDefinitionLabel } from "@/entities/nodes/object/domain/filter-definition";
import { FieldFilterForm } from "@/entities/nodes/object/ui/filters/field-filter-form";
import { FilterResetButton } from "@/entities/nodes/object/ui/filters/filter-reset-button";
import { FilterTag } from "@/entities/nodes/object/ui/filters/filter-tag";
import {
  HIDE_INTERNAL_GROUPS_FILTER,
  HIDE_INTERNAL_GROUPS_ID,
  SHOW_INTERNAL_GROUPS_ID,
} from "@/entities/nodes/object/ui/filters/internal-groups-filter-tag";
import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import type { AttributeKind } from "@/entities/schema/types";

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
  filterDefinitions: Record<string, FilterDefinition>;
  additionalTags?: React.ReactNode;
}

export function ActiveFilterTags({
  filters,
  setFilters,
  filterDefinitions,
  additionalTags,
  ...props
}: ActiveFilterTagsProps) {
  const [editingFilter, setEditingFilter] = useState<FilterDefinition | null>(null);
  const tagElements = useRef(new Map<string, Element>());
  const editTriggerRef = useRef<Element | null>(null);

  const handleRemoveFilter = (filterName: string) => {
    switch (filterName) {
      case HIDE_INTERNAL_GROUPS_ID: {
        setFilters([HIDE_INTERNAL_GROUPS_FILTER, ...filters]);
        return;
      }
      case SHOW_INTERNAL_GROUPS_ID: {
        setFilters(filters.filter((filter) => filter.name !== HIDE_INTERNAL_GROUPS_FILTER.name));
        return;
      }
      case SHOW_AVAILABLE_IP: {
        setFilters(filters.filter((filter) => filter.name !== AVAILABLE_IP_FILTER_NAME));
        return;
      }
      case HIDE_AVAILABLE_IP: {
        setFilters([HIDE_AVAILABLE_IP_FILTER, ...filters]);
        return;
      }
      default: {
        setFilters(filters.filter((f) => f.name !== filterName));
        return;
      }
    }
  };

  const handleSelectionChange = (keys: Selection) => {
    if (keys === "all") return;
    const key = [...keys][0];
    const filterName = key ? String(key) : null;

    if (!filterName) {
      setEditingFilter(null);
      return;
    }

    const parts = filterName.split("__");
    const fieldName = parts.slice(0, -1).join("__");

    switch (filterName) {
      case HIDE_INTERNAL_GROUPS_ID: {
        setFilters([HIDE_INTERNAL_GROUPS_FILTER, ...filters]);
        return;
      }
      case SHOW_INTERNAL_GROUPS_ID: {
        setFilters(filters.filter((filter) => filter.name !== HIDE_INTERNAL_GROUPS_FILTER.name));
        return;
      }
      case SHOW_AVAILABLE_IP: {
        setFilters(filters.filter((filter) => filter.name !== AVAILABLE_IP_FILTER_NAME));
        return;
      }
      case HIDE_AVAILABLE_IP: {
        setFilters([HIDE_AVAILABLE_IP_FILTER, ...filters]);
        return;
      }
    }

    const definition = filterDefinitions[fieldName];

    if (definition) {
      editTriggerRef.current = tagElements.current.get(filterName) ?? null;
      setEditingFilter(definition);
      return;
    }
    return;
  };

  if (filters.length === 0 && !additionalTags) {
    return null;
  }

  return (
    <ScrollArea scrollX scrollBarClassName="hidden">
      <Row className="p-2 pt-0">
        <TagGroup
          aria-label="Active filters"
          selectionMode="single"
          selectedKeys={editingFilter ? [] : []}
          onSelectionChange={handleSelectionChange}
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
              const fieldKey = parts.at(-1);
              if (!fieldKey || parts.length < 2) {
                return null;
              }

              const fieldName = parts.slice(0, -1).join("__");
              const definition = filterDefinitions[fieldName];

              if (!definition) {
                return null;
              }

              return (
                <EditableFilterTag
                  key={filter.name}
                  filter={filter}
                  fieldKey={fieldKey}
                  filterDefinition={definition}
                  ref={(el: HTMLDivElement | null) => {
                    if (el) tagElements.current.set(filter.name, el);
                  }}
                />
              );
            })}
          </TagList>
        </TagGroup>

        {filters.length > 0 && <FilterResetButton />}
      </Row>

      {editingFilter && (
        <Popover
          triggerRef={editTriggerRef}
          isOpen
          onOpenChange={(isOpen) => {
            if (!isOpen) setEditingFilter(null);
          }}
          placement="bottom start"
        >
          <FieldFilterForm definition={editingFilter} onSuccess={() => setEditingFilter(null)} />
        </Popover>
      )}
    </ScrollArea>
  );
}

interface EditableFilterTagProps {
  ref?: React.Ref<HTMLDivElement>;
  filter: Filter;
  fieldKey: string;
  filterDefinition: FilterDefinition;
}

function EditableFilterTag({ ref, filter, fieldKey, filterDefinition }: EditableFilterTagProps) {
  const display = getFilterTagDisplay({
    filter,
    fieldKey,
    filterDefinition,
  });

  if (!display) return null;

  const { label, condition, value } = display;

  return <FilterTag ref={ref} id={filter.name} label={label} condition={condition} value={value} />;
}

type FilterTagDisplay = { label: React.ReactNode; condition: string; value: React.ReactNode };

export function getFilterTagDisplay({
  filter,
  fieldKey,
  filterDefinition,
}: {
  filter: Filter;
  fieldKey: string;
  filterDefinition: FilterDefinition;
}): FilterTagDisplay | null {
  const name = getFilterDefinitionLabel(filterDefinition);
  const isRelationship =
    filterDefinition.type === "relationship" || filterDefinition.type === "metadata-user";

  if (fieldKey === "value" || fieldKey === "values") {
    if (filterDefinition.type !== "attribute") return null;

    return {
      label: name,
      condition: "contains",
      value: formatAttributeFilterValue({
        kind: filterDefinition.schema.kind as AttributeKind,
        value: filter.value,
      }),
    };
  }

  if (fieldKey === "ids") {
    if (!isRelationship) return null;
    if (!Array.isArray(filter.value)) return null;

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
    if (isRelationship) return null;

    return {
      label: name,
      condition: fieldKey,
      value: formatFullDate(filter.value as string | number | Date),
    };
  }

  return null;
}
