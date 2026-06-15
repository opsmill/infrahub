import { Icon } from "@iconify-icon/react";
import { Button, ListBox, ListBoxItem, Popover, PopoverTrigger } from "@infrahub/ui";
import { ChevronRightIcon } from "lucide-react";
import type React from "react";
import { useRef, useState } from "react";
import type { Key } from "react-aria-components";

import { Autocomplete } from "@/shared/components/aria/autocomplete";
import { isFieldFiltered } from "@/shared/hooks/is-field-filtered";
import type { Filter } from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";

import {
  type FilterDefinition,
  getFilterDefinitionLabel,
  getFilterDefinitionName,
} from "@/entities/nodes/object/domain/filter-definition";
import { FieldFilterForm } from "@/entities/nodes/object/ui/filters/field-filter-form";
import { getFilterDefinitionIcon } from "@/entities/nodes/object/ui/filters/get-filter-definition-icon";
import { getFilterDefinitions } from "@/entities/nodes/object/ui/filters/get-filter-definitions";
import { getFilterPickerCount } from "@/entities/nodes/object/ui/filters/get-filter-picker-count";
import type { ModelSchema } from "@/entities/schema/types";
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

  const fields: FilterDefinition[] = getFilterDefinitions(schema);

  const activeFieldDefinition = fields.find((f) => getFilterDefinitionName(f) === selectedField);

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
        <Button variant="ghost" size="sm" className="rounded-xl border-gray-300">
          <Icon icon="mdi:filter-variant" className="text-base" />
          Filter
          {filterCount > 0 && <FilterCountBadge count={filterCount} />}
        </Button>

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
              {fields.map((field) => {
                const name = getFilterDefinitionName(field);
                return (
                  <FilterPickerItem
                    key={name}
                    definition={field}
                    hasActiveFilter={filters.some((f) => isFieldFiltered(f, name))}
                    ref={(el: HTMLDivElement | null) => {
                      if (el) itemElements.current.set(name, el);
                    }}
                  />
                );
              })}
            </ListBox>
          </Autocomplete>
        </Popover>
      </PopoverTrigger>

      {selectedField && activeFieldDefinition && (
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
          <FieldFilterForm definition={activeFieldDefinition} onSuccess={closePicker} />
        </Popover>
      )}
    </>
  );
}

interface FilterPickerItemProps {
  definition: FilterDefinition;
  hasActiveFilter: boolean;
  ref?: React.Ref<HTMLDivElement>;
}

function FilterPickerItem({ definition, hasActiveFilter, ref }: FilterPickerItemProps) {
  const name = getFilterDefinitionName(definition);
  const label = getFilterDefinitionLabel(definition);

  return (
    <ListBoxItem id={name} textValue={label} selectionIndicator="highlight" ref={ref}>
      {definition.type === "relationship" ? (
        <FieldSchemaIcon fieldSchema={definition.schema} />
      ) : (
        <Icon icon={getFilterDefinitionIcon(definition)} />
      )}
      <span className="mr-auto">{label}</span>
      {hasActiveFilter && <ActiveFilterIndicator />}
      <ChevronRightIcon className={classNames("size-3.5")} />
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
