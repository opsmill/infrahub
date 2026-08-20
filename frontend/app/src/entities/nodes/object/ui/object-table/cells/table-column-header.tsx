import { Menu, MenuItem, MenuSeparator, MenuTrigger, Popover, SubmenuTrigger } from "@infrahub/ui";
import { ArrowDownIcon, ArrowUpDownIcon, ArrowUpIcon, ListFilterIcon } from "lucide-react";
import React from "react";
import { Button } from "react-aria-components";

import { Row } from "@/shared/components/container";
import {
  cellHeaderInteractiveStyle,
  cellHeaderStyle,
  cellsStyle,
} from "@/shared/components/table/style";
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
import { findSortForField } from "@/entities/nodes/sort/domain/rules/find-sort-for-field";
import { isSortableAttribute } from "@/entities/nodes/sort/domain/rules/is-sortable-attribute";
import { isSortableRelationship } from "@/entities/nodes/sort/domain/rules/is-sortable-relationship";
import {
  buildAttributeSortField,
  buildRelationshipSortField,
} from "@/entities/nodes/sort/domain/rules/sort-field";
import { useSort } from "@/entities/nodes/sort/ui/hooks/use-sort";
import { SortDirectionMenuItem } from "@/entities/nodes/sort/ui/sort-direction-menu-item";
import { SortableAttributeMenuItem } from "@/entities/nodes/sort/ui/sortable-attribute-menu-item";
import type {
  AttributeSchema,
  ModelSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";
import { getRelationshipLabel } from "@/entities/schema/domain/rules/get-relationship-label";
import { isRelationshipSchema } from "@/entities/schema/domain/rules/is-relationship-schema";
import { FieldSchemaIcon } from "@/entities/schema/ui/field-schema-icon";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface TableColumnHeaderProps {
  columnSchema: AttributeSchema | RelationshipSchema;
  schema?: ModelSchema;
  isDisabled?: boolean;
  className?: string;
}

export function TableColumnHeader({
  columnSchema,
  schema,
  isDisabled,
  className,
}: TableColumnHeaderProps) {
  if (isDisabled) {
    return <TableColumnHeaderSimple columnSchema={columnSchema} className={className} />;
  }

  if (schema && !isRelationshipSchema(columnSchema) && isSortableAttribute(columnSchema)) {
    return (
      <SortableAttributeColumnHeader
        schema={schema}
        attributeSchema={columnSchema}
        className={className}
      />
    );
  }

  if (schema && isRelationshipSchema(columnSchema) && isSortableRelationship(columnSchema)) {
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

interface SortableAttributeColumnHeaderProps {
  schema: ModelSchema;
  attributeSchema: AttributeSchema;
  className?: string;
}

function SortableAttributeColumnHeader({
  schema,
  attributeSchema,
  className,
}: SortableAttributeColumnHeaderProps) {
  const { customSort, setCustomSort } = useSort(schema);
  const activeSort = findSortForField(customSort, attributeSchema);

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
  const activeSort = findSortForField(customSort, relationshipSchema);
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

  const label = getRelationshipLabel(relationshipSchema, peerSchema);

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
              {sortableAttributes.map((attribute) => {
                const field = buildRelationshipSortField(
                  relationshipSchema.name,
                  buildAttributeSortField(attribute.name)
                );

                return (
                  <SortableAttributeMenuItem
                    key={attribute.name}
                    attribute={attribute}
                    activeDirection={activeSort?.field === field ? activeSort.direction : undefined}
                    onSelect={(sort) => selectSort({ ...sort, field })}
                  />
                );
              })}
            </Menu>
          </Popover>
        </SubmenuTrigger>
      }
    />
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
  const [showFilterForm, setShowFilterForm] = React.useState(false);
  const triggerRef = React.useRef<HTMLButtonElement>(null);
  const currentColumnFilters = filters.find((f) => isFieldFiltered(f, columnSchema.name));
  const isRelationship = isRelationshipSchema(columnSchema);
  const { schema: peerSchema } = useSchema(isRelationship ? columnSchema.peer : undefined);
  const label = isRelationship
    ? getRelationshipLabel(columnSchema, peerSchema)
    : (columnSchema.label ?? columnSchema.name);

  const closeFilterForm = () => {
    setShowFilterForm(false);
  };

  return (
    <>
      <MenuTrigger>
        <Button
          ref={triggerRef}
          className={classNames(cellsStyle, cellHeaderStyle, cellHeaderInteractiveStyle, className)}
        >
          <FieldSchemaIcon fieldSchema={columnSchema} />

          <span className="mr-2 truncate">{label}</span>
          <Row className="ml-auto min-w-4 justify-end">
            {activeSort &&
              (activeSort.direction === SORT_DIRECTION.DESC ? (
                <>
                  <ArrowDownIcon className="size-4 text-indigo-700" />
                  <span className="sr-only">sorted descending</span>
                </>
              ) : (
                <>
                  <ArrowUpIcon className="size-4 text-indigo-700" />
                  <span className="sr-only">sorted ascending</span>
                </>
              ))}
            {currentColumnFilters && <ListFilterIcon className="size-4 text-indigo-700" />}
          </Row>
        </Button>

        <Popover placement="bottom start">
          <Menu aria-label={`${label} column options`} variant="picker">
            {sortItems ? (
              <>
                {sortItems}
                <MenuSeparator />
              </>
            ) : null}
            <MenuItem textValue="Filter" onAction={() => setShowFilterForm(true)}>
              <ListFilterIcon />
              <span>Filter</span>
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
        {isRelationshipSchema(columnSchema) ? (
          <RelationshipFilterForm relationshipSchema={columnSchema} onSuccess={closeFilterForm} />
        ) : (
          <AttributeFilterForm attributeSchema={columnSchema} onSuccess={closeFilterForm} />
        )}
      </Popover>
    </>
  );
}
