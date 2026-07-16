import { Icon } from "@iconify-icon/react";
import { Menu, MenuItem, MenuSection, MenuSeparator, MenuTrigger, Popover } from "@infrahub/ui";
import { CheckIcon } from "lucide-react";
import type React from "react";
import { useRef, useState } from "react";
import { Button } from "react-aria-components";

import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { classNames } from "@/shared/utils/common";

import { isFieldFiltered } from "@/entities/nodes/filters/domain/rules/is-field-filtered";
import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";
import { AttributeFilterForm } from "@/entities/nodes/object/ui/filters/attribute-filter-form";
import { RelationshipFilterForm } from "@/entities/nodes/object/ui/filters/relationship-filter-form";
import { TableColumnHeaderSimple } from "@/entities/nodes/object/ui/object-table/cells/table-column-header-simple";
import {
  SORT_DIRECTION,
  type Sort,
  type SortDirection,
} from "@/entities/nodes/sort/domain/model/sort";
import { getColumnActiveSort } from "@/entities/nodes/sort/domain/rules/get-column-active-sort";
import { isSortableAttribute } from "@/entities/nodes/sort/domain/rules/is-sortable-attribute";
import { buildAttributeSortField } from "@/entities/nodes/sort/domain/rules/sort-field";
import { useSort } from "@/entities/nodes/sort/ui/hooks/use-sort";
import type {
  AttributeSchema,
  ModelSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";
import { FieldSchemaIcon } from "@/entities/schema/ui/field-schema-icon";

export interface TableColumnHeaderProps {
  columnSchema: AttributeSchema | RelationshipSchema;
  /** Enables the sort menu entries; without it the menu offers filtering only. */
  schema?: ModelSchema;
  disabled?: boolean;
  className?: string;
}

export function TableColumnHeader({
  columnSchema,
  schema,
  disabled,
  className,
}: TableColumnHeaderProps) {
  if (disabled) {
    return <TableColumnHeaderSimple columnSchema={columnSchema} className={className} />;
  }

  if (schema && !("peer" in columnSchema) && isSortableAttribute(columnSchema)) {
    return (
      <SortableColumnHeader schema={schema} attributeSchema={columnSchema} className={className} />
    );
  }

  return <ColumnHeaderMenu columnSchema={columnSchema} className={className} />;
}

interface SortableColumnHeaderProps {
  schema: ModelSchema;
  attributeSchema: AttributeSchema;
  className?: string;
}

function SortableColumnHeader({ schema, attributeSchema, className }: SortableColumnHeaderProps) {
  const { customSort, setCustomSort } = useSort(schema);
  const activeSort = getColumnActiveSort(customSort, attributeSchema);

  const selectSortDirection = (direction: SortDirection) => {
    if (activeSort?.direction === direction) {
      setCustomSort(null);
      return;
    }
    setCustomSort([{ field: buildAttributeSortField(attributeSchema.name), direction }]);
  };

  return (
    <ColumnHeaderMenu
      columnSchema={attributeSchema}
      className={className}
      activeSort={activeSort}
      sortItems={
        <MenuSection selectionMode="single" selectedKeys={activeSort ? [activeSort.direction] : []}>
          <SortDirectionMenuItem direction={SORT_DIRECTION.ASC} onSelect={selectSortDirection}>
            Sort ascending
          </SortDirectionMenuItem>
          <SortDirectionMenuItem direction={SORT_DIRECTION.DESC} onSelect={selectSortDirection}>
            Sort descending
          </SortDirectionMenuItem>
        </MenuSection>
      }
    />
  );
}

interface SortDirectionMenuItemProps {
  direction: SortDirection;
  onSelect: (direction: SortDirection) => void;
  children: string;
}

function SortDirectionMenuItem({ direction, onSelect, children }: SortDirectionMenuItemProps) {
  return (
    <MenuItem id={direction} textValue={children} onAction={() => onSelect(direction)}>
      {({ isSelected }) => (
        <>
          {children}
          {isSelected && <CheckIcon className="ml-auto" />}
        </>
      )}
    </MenuItem>
  );
}

interface ColumnHeaderMenuProps {
  columnSchema: AttributeSchema | RelationshipSchema;
  className?: string;
  activeSort?: Sort | null;
  sortItems?: React.ReactNode;
}

function ColumnHeaderMenu({
  columnSchema,
  className,
  activeSort = null,
  sortItems,
}: ColumnHeaderMenuProps) {
  const [filters] = useFilters();
  const [showFilterForm, setShowFilterForm] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const currentColumnFilters = filters.find((f) => isFieldFiltered(f, columnSchema.name));
  const label = columnSchema.label ?? columnSchema.name;

  const closeFilterForm = () => {
    setShowFilterForm(false);
  };

  return (
    <>
      <MenuTrigger>
        <Button ref={triggerRef} className={classNames(cellsStyle, cellHeaderStyle, className)}>
          <FieldSchemaIcon fieldSchema={columnSchema} />

          <span className="mr-2 truncate">{label}</span>
          {activeSort && (
            <>
              <Icon
                icon={
                  activeSort.direction === SORT_DIRECTION.DESC ? "mdi:arrow-down" : "mdi:arrow-up"
                }
                className="text-indigo-700 text-lg"
              />
              <span className="sr-only">
                {activeSort.direction === SORT_DIRECTION.DESC
                  ? "sorted descending"
                  : "sorted ascending"}
              </span>
            </>
          )}
          <Icon
            icon="mdi:filter-variant"
            className={classNames(
              "ml-auto text-lg",
              currentColumnFilters ? "text-indigo-700" : "invisible"
            )}
          />
        </Button>

        <Popover placement="bottom start">
          <Menu aria-label={`${label} column options`}>
            {sortItems}
            {sortItems ? <MenuSeparator /> : null}
            <MenuItem onAction={() => setShowFilterForm(true)}>Filter…</MenuItem>
          </Menu>
        </Popover>
      </MenuTrigger>

      <Popover
        triggerRef={triggerRef}
        isOpen={showFilterForm}
        onOpenChange={setShowFilterForm}
        placement="bottom start"
      >
        {"peer" in columnSchema ? (
          <RelationshipFilterForm relationshipSchema={columnSchema} onSuccess={closeFilterForm} />
        ) : (
          <AttributeFilterForm attributeSchema={columnSchema} onSuccess={closeFilterForm} />
        )}
      </Popover>
    </>
  );
}
