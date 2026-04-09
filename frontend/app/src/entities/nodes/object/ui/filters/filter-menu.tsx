import { Icon } from "@iconify-icon/react";
import { ChevronRightIcon } from "lucide-react";
import { useRef, useState } from "react";
import { Button as AriaButton, type Selection } from "react-aria-components";

import { Autocomplete } from "@/shared/components/aria/autocomplete";
import { ListBox, ListBoxItem } from "@/shared/components/aria/list-box";
import { Popover, PopoverTrigger } from "@/shared/components/aria/popover";
import { focusVisibleStyle } from "@/shared/components/aria/style-rac";
import { isFieldFiltered } from "@/shared/hooks/is-field-filtered";
import type { Filter } from "@/shared/hooks/useFilters";
import { classNames, sortByOrderWeight } from "@/shared/utils/common";

import { getFilterMenuCount } from "@/entities/nodes/object/domain/get-filter-menu-count";
import { ALL_METADATA_FILTERS } from "@/entities/nodes/object/domain/metadata-filter-definitions";
import { FieldFilterForm } from "@/entities/nodes/object/ui/filters/field-filter-form";
import type { ModelSchema } from "@/entities/schema/types";
import { FieldSchemaIcon } from "@/entities/schema/ui/field-schema-icon";

interface FilterMenuProps {
  schema: ModelSchema;
  filters: Filter[];
}

export function FilterMenu({ schema, filters }: FilterMenuProps) {
  const [open, setOpen] = useState(false);
  const [selectedField, setSelectedField] = useState<string | null>(null);

  const filterCount = getFilterMenuCount(schema, filters);

  const itemElements = useRef(new Map<string, Element>());
  const activeItemRef = useRef<Element | null>(null);

  const closeMenu = () => {
    setOpen(false);
    setSelectedField(null);
  };

  const fields = [
    ...sortByOrderWeight([...(schema.attributes ?? []), ...(schema.relationships ?? [])]),
    ...ALL_METADATA_FILTERS,
  ];
  const activeFieldSchema = fields.find((f) => f.name === selectedField);

  const handleSelectionChange = (keys: Selection) => {
    if (keys === "all") return;
    const key = [...keys][0];
    const fieldName = key ? String(key) : null;
    activeItemRef.current = fieldName ? (itemElements.current.get(fieldName) ?? null) : null;
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
          {filterCount > 0 && (
            <span className="inline-flex size-4.5 shrink-0 items-center justify-center rounded-full bg-stone-200 px-1 text-stone-600 text-xs">
              {filterCount}
            </span>
          )}
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
              onSelectionChange={handleSelectionChange}
              className="max-h-72 p-1"
            >
              {fields.map((field) => {
                const hasActiveFilter = filters.some((f) => isFieldFiltered(f, field.name));

                return (
                  <ListBoxItem
                    key={field.name}
                    id={field.name}
                    textValue={field.label ?? field.name}
                    className={({ isSelected }) =>
                      classNames(isSelected && "bg-stone-700/10 text-stone-800")
                    }
                    ref={(el: HTMLDivElement | null) => {
                      if (el) itemElements.current.set(field.name, el);
                    }}
                  >
                    {({ isSelected }) => (
                      <>
                        <FieldSchemaIcon fieldSchema={field} />
                        {field.label}
                        {hasActiveFilter && (
                          <span className="ml-auto size-1 rounded-full bg-custom-blue-700" />
                        )}
                        <ChevronRightIcon
                          className={classNames(
                            "size-3.5",
                            !hasActiveFilter && "ml-auto",
                            isSelected && "opacity-0"
                          )}
                        />
                      </>
                    )}
                  </ListBoxItem>
                );
              })}
            </ListBox>
          </Autocomplete>
        </Popover>
      </PopoverTrigger>

      {selectedField && activeFieldSchema && (
        <Popover
          className="filter-form-popover"
          triggerRef={activeItemRef}
          offset={8}
          isOpen
          onOpenChange={(isOpen) => {
            if (!isOpen) setSelectedField(null);
          }}
          placement="end top"
        >
          <FieldFilterForm fieldSchema={activeFieldSchema} onSuccess={closeMenu} />
        </Popover>
      )}
    </>
  );
}
