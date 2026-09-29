import { Autocomplete, Button, ListBox, ListBoxItem, Popover, PopoverTrigger } from "@infrahub/ui";
import { ChevronRightIcon } from "lucide-react";
import type React from "react";
import { useRef, useState } from "react";
import type { Key } from "react-aria-components";

import { CountBadge } from "@/shared/components/buttons/count-badge";
import { Icon } from "@/shared/components/display/icon";
import { classNames } from "@/shared/utils/common";

import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import { isFieldFiltered } from "@/entities/nodes/filters/domain/rules/is-field-filtered";
import type { FilterDefinition } from "@/entities/nodes/object/domain/model/filter-definition";
import {
  getFilterDefinitionLabel,
  getFilterDefinitionName,
} from "@/entities/nodes/object/domain/rules/filter-definition";
import { FieldFilterForm } from "@/entities/nodes/object/ui/filters/field-filter-form";
import type { FilterConditionSelectProps } from "@/entities/nodes/object/ui/filters/filter-condition-select";
import { getFilterDefinitionIcon } from "@/entities/nodes/object/ui/filters/get-filter-definition-icon";
import { getFilterPickerCount } from "@/entities/nodes/object/ui/filters/get-filter-picker-count";
import { FieldSchemaIcon } from "@/entities/schema/ui/field-schema-icon";

interface FilterPickerProps {
  filterDefinitions: FilterDefinition[];
  /** Narrows every field's condition menu to the ones the caller's backend contract can honour. */
  filterConditions?: FilterConditionSelectProps["filterConditions"];
  filters: Filter[];
}

export function FilterPicker({ filterDefinitions, filterConditions, filters }: FilterPickerProps) {
  const [open, setOpen] = useState(false);
  const [selectedField, setSelectedField] = useState<string | null>(null);

  const filterCount = getFilterPickerCount(filterDefinitions, filters);

  const itemElements = useRef(new Map<string, Element>());
  const triggerRef = useRef<Element | null>(null);

  const closePicker = () => {
    setOpen(false);
    setSelectedField(null);
  };

  const activeFieldDefinition = filterDefinitions.find(
    (f) => getFilterDefinitionName(f) === selectedField
  );

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
        <Button variant="input" size="sm">
          <Icon icon="mdi:filter-variant" className="text-base" />
          Filter
          {filterCount > 0 && <CountBadge count={filterCount} />}
        </Button>

        <Popover
          placement="bottom start"
          shouldCloseOnInteractOutside={(element) => !element.closest(".filter-form-popover")}
        >
          <Autocomplete>
            <ListBox
              aria-label="Filter fields"
              selectionMode="single"
              selectionIndicator="highlight"
              selectedKeys={selectedField ? [selectedField] : []}
              onAction={handleAction}
              className="max-h-72"
            >
              {filterDefinitions.map((field) => {
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
          <FieldFilterForm
            definition={activeFieldDefinition}
            filterConditions={filterConditions}
            onSuccess={closePicker}
          />
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
    <ListBoxItem id={name} textValue={label} ref={ref}>
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

function ActiveFilterIndicator() {
  return <span className="size-1 rounded-full bg-accent" />;
}
