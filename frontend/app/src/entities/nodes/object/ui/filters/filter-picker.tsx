import { Icon } from "@iconify-icon/react";
import { ChevronRightIcon } from "lucide-react";
import type React from "react";
import { useRef, useState } from "react";
import { Button as AriaButton, type Key } from "react-aria-components";

import { Autocomplete } from "@/shared/components/aria/autocomplete";
import { ListBox, ListBoxItem } from "@/shared/components/aria/list-box";
import { Popover, PopoverTrigger } from "@/shared/components/aria/popover";
import { focusVisibleStyle } from "@/shared/components/aria/style-rac";
import { isFieldFiltered } from "@/shared/hooks/is-field-filtered";
import type { Filter } from "@/shared/hooks/useFilters";
import { classNames, sortByOrderWeight } from "@/shared/utils/common";

import { getFilterPickerCount } from "@/entities/nodes/object/domain/get-filter-picker-count";
import {
  ALL_METADATA_FILTERS,
  isMetadataFilter,
} from "@/entities/nodes/object/domain/metadata-filter-definitions";
import { FieldFilterForm } from "@/entities/nodes/object/ui/filters/field-filter-form";
import { MetadataFilterForm } from "@/entities/nodes/object/ui/filters/metadata-filter-form";
import type { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import { FieldSchemaIcon } from "@/entities/schema/ui/field-schema-icon";

interface FilterPickerProps {
  schema: ModelSchema;
  filters: Filter[];
}

export function FilterPicker({ schema, filters }: FilterPickerProps) {
  const [open, setOpen] = useState(false);
  const [selectedField, setSelectedField] = useState<string | null>(null);

  const filterCount = getFilterPickerCount(schema, filters);

  const itemElements = useRef(new Map<string, Element>());
  const triggerRef = useRef<Element | null>(null);

  const closePicker = () => {
    setOpen(false);
    setSelectedField(null);
  };

  const fields = [
    ...sortByOrderWeight([...(schema.attributes ?? []), ...(schema.relationships ?? [])]),
    ...ALL_METADATA_FILTERS,
  ];
  const activeFieldSchema = fields.find((f) => f.name === selectedField);

  const handleAction = (key: Key) => {
    const fieldName = String(key);
    triggerRef.current = itemElements.current.get(fieldName) ?? null;
    setSelectedField(fieldName);
  };

  return (
    <>
      <PopoverTrigger
        isOpen={open}
        onOpenChange={(isOpen) => {
          setOpen(isOpen);
          if (!isOpen) setSelectedField(null);
        }}
      >
        <AriaButton
          className={classNames(
            focusVisibleStyle,
            "inline-flex h-8 shrink-0 items-center gap-1 rounded-xl border border-stone-300 px-2 text-sm"
          )}
        >
          <Icon icon="mdi:filter-variant" className="text-base" />
          Filter
          {filterCount > 0 && <FilterCountBadge count={filterCount} />}
        </AriaButton>

        <Popover
          placement="bottom start"
          shouldCloseOnInteractOutside={(element) => !element.closest(".filter-form-popover")}
        >
          <Autocomplete>
            <ListBox
              aria-label="Filter fields"
              selectionMode="single"
              selectedKeys={selectedField ? [selectedField] : []}
              onAction={handleAction}
              className="max-h-72 p-1"
            >
              {fields.map((field) => (
                <FilterPickerItem
                  key={field.name}
                  field={field}
                  hasActiveFilter={filters.some((f) => isFieldFiltered(f, field.name))}
                  ref={(el: HTMLDivElement | null) => {
                    if (el) itemElements.current.set(field.name, el);
                  }}
                />
              ))}
            </ListBox>
          </Autocomplete>
        </Popover>
      </PopoverTrigger>

      {selectedField && activeFieldSchema && (
        <Popover
          className="filter-form-popover"
          triggerRef={triggerRef}
          offset={8}
          isOpen
          onOpenChange={(isOpen) => {
            if (!isOpen) setSelectedField(null);
          }}
          placement="end top"
        >
          {isMetadataFilter(activeFieldSchema.name) ? (
            <MetadataFilterForm metadataFilter={activeFieldSchema} onSuccess={closePicker} />
          ) : (
            <FieldFilterForm fieldSchema={activeFieldSchema} onSuccess={closePicker} />
          )}
        </Popover>
      )}
    </>
  );
}

interface FilterPickerItemProps {
  field: AttributeSchema | RelationshipSchema;
  hasActiveFilter: boolean;
  ref?: React.Ref<HTMLDivElement>;
}

function FilterPickerItem({ field, hasActiveFilter, ref }: FilterPickerItemProps) {
  return (
    <ListBoxItem
      id={field.name}
      textValue={field.label ?? field.name}
      className={({ isSelected }) => classNames(isSelected && "bg-stone-700/10 text-stone-800")}
      ref={ref}
    >
      {({ isSelected }) => (
        <>
          <FieldSchemaIcon fieldSchema={field} />
          <span className="mr-auto">{field.label}</span>
          {hasActiveFilter && <ActiveFilterIndicator />}
          <ChevronRightIcon className={classNames("size-3.5", isSelected && "opacity-0")} />
        </>
      )}
    </ListBoxItem>
  );
}

function FilterCountBadge({ count }: { count: number }) {
  return (
    <span className="inline-flex size-5 shrink-0 items-center justify-center rounded-full bg-stone-200 px-1 text-stone-600 text-xs">
      {count}
    </span>
  );
}

function ActiveFilterIndicator() {
  return <span className="size-1 rounded-full bg-custom-blue-700" />;
}
