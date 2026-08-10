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
import { AddSortButton } from "@/entities/nodes/sort/ui/add-sort/add-sort-button";
import { AddSortPicker } from "@/entities/nodes/sort/ui/add-sort/add-sort-picker";
import { useSort } from "@/entities/nodes/sort/ui/hooks/use-sort";
import { useSortableFields } from "@/entities/nodes/sort/ui/hooks/use-sortable-fields";
import { DIRECTION_OPTIONS, PEER_LABEL_SEPARATOR } from "@/entities/nodes/sort/ui/sort-options";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

interface SortEditorProps {
  schema: ModelSchema;
}
export function SortEditor({ schema }: SortEditorProps) {
  const { appliedSort, setCustomSort } = useSort(schema);

  const addSort = (newSort: Sort) => {
    const withoutField = appliedSort.filter((existing) => existing.field !== newSort.field);
    setCustomSort([...withoutField, newSort]);
  };

  if (appliedSort.length === 0) {
    return <AddSortPicker schema={schema} onSelect={addSort} />;
  }

  return (
    <Col className="items-start gap-1 p-1">
      <SortListContainer schema={schema}>
        <SortableList aria-label="Sort keys" items={appliedSort} onReorder={setCustomSort}>
          {(entry) => <SortEditorRow id={entry.field} schema={schema} sort={entry} />}
        </SortableList>
      </SortListContainer>

      <AddSortButton
        schema={schema}
        activeFields={new Set(appliedSort.map((sort) => sort.field))}
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
  const { customSort, setCustomSort, defaultSort } = useSort(schema);

  const isDefaultOrder = customSort === null;

  if (isDefaultOrder) {
    return (
      <div className="inset-shadow-[0_1px_2px_rgb(255,255,255),0_1px_4px_rgba(0,0,0,0.1)] rounded-lg border bg-stone-200/50 shadow-[0_1px_1px_rgba(0,0,0,0.02)]">
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
        <Button
          variant="ghost"
          size="xxs"
          className="ml-auto text-stone-500"
          onPress={() => setCustomSort([])}
        >
          {defaultSort ? (
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
  schema: ModelSchema;
  value: SortField;
  onChange: (field: SortField) => void;
}

/**
 * Readable label for a sort field the picker doesn't offer — a schema default order can target an
 * attribute sub-property (e.g. IP prefixes sort on `prefix__version`) while the picker only exposes
 * `__value` fields. Renders as "Prefix › version", matching the peer-attribute label style.
 */
export function describeUnlistedSortField(field: SortField, schema: ModelSchema): string {
  const [attributeName, ...propertySegments] = field.split("__");
  const attributeLabel =
    schema.attributes?.find((attribute) => attribute.name === attributeName)?.label ??
    attributeName ??
    field;
  const property = propertySegments
    .map((segment) => segment.replaceAll("_", " "))
    .join(PEER_LABEL_SEPARATOR);
  return property ? `${attributeLabel}${PEER_LABEL_SEPARATOR}${property}` : attributeLabel;
}

function SortFieldSelect({ schema, value, onChange }: SortFieldSelectProps) {
  const { appliedSort } = useSort(schema);
  const sortableFields = useSortableFields(schema);

  const fieldsUsedByOtherRows = new Set(
    appliedSort.filter((entry) => entry.field !== value).map((entry) => entry.field)
  );
  const unusedSortableFields = sortableFields.filter(
    (field) => !fieldsUsedByOtherRows.has(field.field)
  );

  // Without an item matching the selected key the trigger renders blank, so surface an unlisted
  // sort field (e.g. a sub-property default order) as a disabled, read-only item.
  const unlistedFieldLabel = unusedSortableFields.some((field) => field.field === value)
    ? null
    : describeUnlistedSortField(value, schema);

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
            {unlistedFieldLabel && (
              <SelectItem id={value} isDisabled>
                {unlistedFieldLabel}
              </SelectItem>
            )}
            {unusedSortableFields.map(({ field, label }) => (
              <SelectItem key={field} id={field}>
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
  const { customSort, setCustomSort, appliedSort, defaultSort } = useSort(schema);

  const remove = () => setCustomSort(appliedSort.filter((entry) => entry.field !== sort.field));

  // Removing the only row while on the schema default is a no-op (it snaps back), so hide it.
  const canRemove = !(customSort === null && appliedSort.length === 1);

  // Deleting the last remaining row reverts to the schema default, so frame it as a reset.
  const willResetsToDefault = canRemove && appliedSort.length === 1 && !!defaultSort?.length;

  if (!canRemove) {
    return (
      <Tooltip message="This is the default order. Edit it or add a sort to customize.">
        <Button
          variant="ghost"
          size="sm"
          shape="square"
          aria-label="Why this sort can't be removed"
          isDisabledAndFocusable
        >
          <InfoIcon />
        </Button>
      </Tooltip>
    );
  }

  if (willResetsToDefault) {
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

interface SortEditorRowProps {
  // Required on the wrapper itself: the collection keys rows by the rendered element's `id` prop.
  id: SortField;
  schema: ModelSchema;
  sort: Sort;
}

function SortEditorRow({ id, schema, sort }: SortEditorRowProps) {
  const { setCustomSort, appliedSort } = useSort(schema);

  const replaceField = (field: SortField) =>
    setCustomSort(
      appliedSort.map((entry) => (entry.field === sort.field ? { ...entry, field } : entry))
    );

  const replaceDirection = (direction: SortDirection) =>
    setCustomSort(
      appliedSort.map((entry) => (entry.field === sort.field ? { ...entry, direction } : entry))
    );

  return (
    <SortableItem id={id} textValue={id}>
      <SortFieldSelect schema={schema} value={sort.field} onChange={replaceField} />

      <SortDirectionSelect value={sort.direction} onChange={replaceDirection} />

      <RemoveSortButton schema={schema} sort={sort} />
    </SortableItem>
  );
}
