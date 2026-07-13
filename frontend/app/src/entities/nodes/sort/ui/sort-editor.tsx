import {
  Autocomplete,
  Button,
  ListBox,
  Popover,
  Select,
  SelectItem,
  SelectList,
  SelectTrigger,
  SortableItem,
  SortableList,
  Tooltip,
} from "@infrahub/ui";
import { CheckIcon, InfoIcon, RotateCcwIcon, SlidersHorizontalIcon, XIcon } from "lucide-react";
import type React from "react";

import { Col, Row } from "@/shared/components/container";

import type { Sort, SortDirection, SortField } from "@/entities/nodes/sort/domain/model/sort";
import { getSchemaDefaultSort } from "@/entities/nodes/sort/domain/rules/get-schema-default-sort";
import { AddSortButton } from "@/entities/nodes/sort/ui/add-sort/add-sort-button";
import { AddSortPicker } from "@/entities/nodes/sort/ui/add-sort/add-sort-picker";
import { useSort } from "@/entities/nodes/sort/ui/hooks/use-sort";
import { useSortableFields } from "@/entities/nodes/sort/ui/hooks/use-sortable-fields";
import { DIRECTION_OPTIONS, type SortableField } from "@/entities/nodes/sort/ui/sort-options";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

interface SortEditorProps {
  schema: ModelSchema;
}
export function SortEditor({ schema }: SortEditorProps) {
  const { sort, setSort } = useSort(schema);

  const currentSort: Sort[] = sort ?? getSchemaDefaultSort(schema) ?? [];

  const addSort = (newSort: Sort) => {
    const withoutField = currentSort.filter((existing) => existing.field !== newSort.field);
    setSort([...withoutField, newSort]);
  };

  if (currentSort.length === 0) {
    return <AddSortPicker schema={schema} onSelect={addSort} />;
  }

  return (
    <Col className="items-start gap-1 p-1">
      <SortListContainer schema={schema}>
        <SortableList aria-label="Sort keys" items={currentSort} onReorder={setSort}>
          {(entry) => (
            <SortableItem id={entry.field} textValue={entry.field}>
              <SortableItemContent schema={schema} sort={entry} />
            </SortableItem>
          )}
        </SortableList>
      </SortListContainer>

      <AddSortButton
        schema={schema}
        activeFields={new Set(currentSort.map((sort) => sort.field))}
        onSelect={addSort}
      />
    </Col>
  );
}

interface SortListContainerProps {
  schema: ModelSchema;
  children: React.ReactNode;
}

function SortListContainer({ schema, children }: SortListContainerProps) {
  const { sort, setSort } = useSort(schema);

  const isDefaultOrder = sort === null;

  if (isDefaultOrder) {
    return (
      <div className="inset-shadow-[0_1px_2px_rgb(255,255,255),0_1px_4px_rgba(0,0,0,0.1)] rounded-lg border border-stone-200 bg-stone-200/50 shadow-[0_1px_1px_rgba(0,0,0,0.02)]">
        <Row className="h-6 pl-2 font-medium text-stone-500 text-xs">
          <CheckIcon className="size-3.5 text-cyan-600" />
          Default order · applied now
        </Row>
        {children}
      </div>
    );
  }

  return (
    <div className="border border-transparent">
      <Row className="h-6 pl-2 font-medium text-stone-500 text-xs">
        <SlidersHorizontalIcon className="size-3.5" />
        Custom order
        <Button variant="ghost" size="xxs" className="ml-auto text-xxs" onPress={() => setSort([])}>
          {getSchemaDefaultSort(schema) ? (
            <>
              <RotateCcwIcon />
              Reset to default
            </>
          ) : (
            <>
              <XIcon />
              Clear sort
            </>
          )}
        </Button>
      </Row>
      {children}
    </div>
  );
}

interface SortFieldSelectProps {
  fields: SortableField[];
  value: SortField;
  onChange: (field: SortField) => void;
}

function SortFieldSelect({ fields, value, onChange }: SortFieldSelectProps) {
  return (
    <Select
      aria-label="Sort field"
      value={value}
      onChange={(key) => onChange(String(key) as SortField)}
      className="flex-1"
    >
      <SelectTrigger size="sm" />

      <Popover placement="bottom start">
        <Autocomplete>
          <ListBox selectionMode="single" className="max-h-72">
            {fields.map(({ field, label }) => (
              <SelectItem key={field} id={field} textValue={label}>
                {label}
              </SelectItem>
            ))}
          </ListBox>
        </Autocomplete>
      </Popover>
    </Select>
  );
}

interface SortDirectionSelectProps {
  value: SortDirection;
  onChange: (direction: SortDirection) => void;
}

function SortDirectionSelect({ value, onChange }: SortDirectionSelectProps) {
  return (
    <Select
      aria-label="Sort direction"
      value={value}
      onChange={(key) => onChange(key as SortDirection)}
      className="w-32"
    >
      <SelectTrigger size="sm" />

      <SelectList items={DIRECTION_OPTIONS} matchTriggerWidth={false}>
        {(option) => <SelectItem>{option.label}</SelectItem>}
      </SelectList>
    </Select>
  );
}

interface RemoveSortButtonProps {
  schema: ModelSchema;
  sort: Sort;
}

function RemoveSortButton({ schema, sort }: RemoveSortButtonProps) {
  const { sort: sortInQsp, setSort } = useSort(schema);
  const currentSort = sortInQsp ?? getSchemaDefaultSort(schema) ?? [];

  const remove = () => setSort(currentSort.filter((entry) => entry.field !== sort.field));

  // Removing the only row while on the schema default is a no-op (it snaps back), so hide it.
  const canRemove = !(sortInQsp === null && currentSort.length === 1);

  // Deleting the last remaining row reverts to the schema default, so frame it as a reset.
  const removeResetsToDefault =
    canRemove && currentSort.length === 1 && (getSchemaDefaultSort(schema)?.length ?? 0) > 0;

  if (!canRemove) {
    return (
      <Tooltip message="This is the default order. Edit it or add a sort to customize.">
        <Button
          variant="ghost"
          size="sm"
          shape="square"
          aria-label="Why this sort can't be removed"
        >
          <InfoIcon />
        </Button>
      </Tooltip>
    );
  }

  if (removeResetsToDefault) {
    return (
      <Tooltip message="Reset to the default order">
        <Button
          variant="ghost"
          size="sm"
          shape="square"
          aria-label="Reset to default"
          onPress={remove}
        >
          <RotateCcwIcon />
        </Button>
      </Tooltip>
    );
  }

  return (
    <Button variant="ghost" size="sm" shape="square" aria-label="Remove sort" onPress={remove}>
      <XIcon />
    </Button>
  );
}

interface SortableItemContentProps {
  schema: ModelSchema;
  sort: Sort;
}

function SortableItemContent({ schema, sort }: SortableItemContentProps) {
  const { sort: sortInQsp, setSort } = useSort(schema);
  const sortableFields = useSortableFields(schema);
  const currentSort = sortInQsp ?? getSchemaDefaultSort(schema) ?? [];

  const fieldsUsedByOtherRows = new Set(
    currentSort.filter((entry) => entry.field !== sort.field).map((entry) => entry.field)
  );
  const availableFields = sortableFields.filter((field) => !fieldsUsedByOtherRows.has(field.field));

  const replaceField = (field: SortField) =>
    setSort(currentSort.map((entry) => (entry.field === sort.field ? { ...entry, field } : entry)));

  const replaceDirection = (direction: SortDirection) =>
    setSort(
      currentSort.map((entry) => (entry.field === sort.field ? { ...entry, direction } : entry))
    );

  return (
    <>
      <SortFieldSelect fields={availableFields} value={sort.field} onChange={replaceField} />

      <SortDirectionSelect value={sort.direction} onChange={replaceDirection} />

      <RemoveSortButton schema={schema} sort={sort} />
    </>
  );
}
