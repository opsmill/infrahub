import { Icon } from "@iconify-icon/react";
import { Menu, MenuItem, MenuSeparator, MenuTrigger, Popover, SubmenuTrigger } from "@infrahub/ui";
import {
  ArrowDownIcon,
  ArrowUpDownIcon,
  ArrowUpIcon,
  CheckIcon,
  ListFilterIcon,
} from "lucide-react";
import type React from "react";
import { useRef, useState } from "react";
import { Button } from "react-aria-components";

import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { classNames, sortByOrderWeight } from "@/shared/utils/common";

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
import { isSortableRelationship } from "@/entities/nodes/sort/domain/rules/is-sortable-relationship";
import {
  buildAttributeSortField,
  buildRelationshipSortField,
} from "@/entities/nodes/sort/domain/rules/sort-field";
import { useSort } from "@/entities/nodes/sort/ui/hooks/use-sort";
import type {
  AttributeSchema,
  ModelSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";
import { FieldSchemaIcon } from "@/entities/schema/ui/field-schema-icon";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

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

  if (schema && "peer" in columnSchema && isSortableRelationship(columnSchema)) {
    return (
      <SortableRelationshipColumnHeader
        schema={schema}
        relationshipSchema={columnSchema}
        className={className}
      />
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
        <>
          <SortDirectionMenuItem
            direction={SORT_DIRECTION.ASC}
            isActive={activeSort?.direction === SORT_DIRECTION.ASC}
            onSelect={selectSortDirection}
          >
            Sort ascending
          </SortDirectionMenuItem>
          <SortDirectionMenuItem
            direction={SORT_DIRECTION.DESC}
            isActive={activeSort?.direction === SORT_DIRECTION.DESC}
            onSelect={selectSortDirection}
          >
            Sort descending
          </SortDirectionMenuItem>
        </>
      }
    />
  );
}

interface SortableRelationshipColumnHeaderProps {
  schema: ModelSchema;
  relationshipSchema: RelationshipSchema;
  className?: string;
}

function SortableRelationshipColumnHeader({
  schema,
  relationshipSchema,
  className,
}: SortableRelationshipColumnHeaderProps) {
  const { customSort, setCustomSort } = useSort(schema);
  const { schema: peerSchema } = useSchema(relationshipSchema.peer);
  const activeSort = getColumnActiveSort(customSort, relationshipSchema);
  const sortableAttributes = sortByOrderWeight(
    (peerSchema?.attributes ?? []).filter(isSortableAttribute)
  );

  if (sortableAttributes.length === 0) {
    return <ColumnHeaderMenu columnSchema={relationshipSchema} className={className} />;
  }

  const selectSort = (sort: Sort) => {
    if (activeSort?.field === sort.field && activeSort.direction === sort.direction) {
      setCustomSort(null);
      return;
    }
    setCustomSort([sort]);
  };

  const label = relationshipSchema.label ?? relationshipSchema.name;

  return (
    <ColumnHeaderMenu
      columnSchema={relationshipSchema}
      className={className}
      activeSort={activeSort}
      sortItems={
        <SubmenuTrigger>
          <MenuItem textValue="Sort by">
            <ArrowUpDownIcon />
            <span>Sort by</span>
          </MenuItem>

          <Popover>
            <Menu aria-label={`Sort by ${label}`}>
              {sortableAttributes.map((attribute) => (
                <PeerAttributeSortMenuItem
                  key={attribute.name}
                  relationshipName={relationshipSchema.name}
                  attribute={attribute}
                  activeSort={activeSort}
                  onSelect={selectSort}
                />
              ))}
            </Menu>
          </Popover>
        </SubmenuTrigger>
      }
    />
  );
}

interface PeerAttributeSortMenuItemProps {
  relationshipName: string;
  attribute: AttributeSchema;
  activeSort: Sort | null;
  onSelect: (sort: Sort) => void;
}

function PeerAttributeSortMenuItem({
  relationshipName,
  attribute,
  activeSort,
  onSelect,
}: PeerAttributeSortMenuItemProps) {
  const field = buildRelationshipSortField(
    relationshipName,
    buildAttributeSortField(attribute.name)
  );
  const label = attribute.label ?? attribute.name;
  const isActive = activeSort?.field === field;

  return (
    <SubmenuTrigger>
      <MenuItem id={field} textValue={label}>
        <FieldSchemaIcon fieldSchema={attribute} />
        <span>{label}</span>
        {isActive && (
          <>
            <CheckIcon className="ml-auto" />
            <span className="sr-only">active sort field</span>
          </>
        )}
      </MenuItem>

      <Popover>
        <Menu
          aria-label={`Sort direction for ${label}`}
          selectionMode="single"
          selectedKeys={activeSort?.field === field ? [activeSort.direction] : []}
        >
          <SortDirectionMenuItem
            direction={SORT_DIRECTION.ASC}
            onSelect={(direction) => onSelect({ field, direction })}
          >
            Ascending
          </SortDirectionMenuItem>
          <SortDirectionMenuItem
            direction={SORT_DIRECTION.DESC}
            onSelect={(direction) => onSelect({ field, direction })}
          >
            Descending
          </SortDirectionMenuItem>
        </Menu>
      </Popover>
    </SubmenuTrigger>
  );
}

interface SortDirectionMenuItemProps {
  direction: SortDirection;
  onSelect: (direction: SortDirection) => void;
  /** Marks the item outside menu selection, for menus where only some items are sort entries. */
  isActive?: boolean;
  children: string;
}

function SortDirectionMenuItem({
  direction,
  onSelect,
  isActive = false,
  children,
}: SortDirectionMenuItemProps) {
  return (
    <MenuItem id={direction} textValue={children} onAction={() => onSelect(direction)}>
      {({ isSelected }) => (
        <>
          {direction === SORT_DIRECTION.DESC ? <ArrowDownIcon /> : <ArrowUpIcon />}
          <span>{children}</span>
          {(isSelected || isActive) && <CheckIcon className="ml-auto" />}
          {isActive && <span className="sr-only">active</span>}
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
          <Menu aria-label={`${label} column options`} variant="picker">
            {sortItems}
            {sortItems ? <MenuSeparator /> : null}
            <MenuItem textValue="Filter…" onAction={() => setShowFilterForm(true)}>
              <ListFilterIcon />
              <span>Filter…</span>
            </MenuItem>
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
