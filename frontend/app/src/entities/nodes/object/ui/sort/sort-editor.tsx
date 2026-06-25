import {
  Autocomplete,
  Button,
  ListBox,
  ListBoxItem,
  Popover,
  Select,
  SelectTrigger,
  SortableItem,
  SortableList,
  Tooltip,
} from "@infrahub/ui";
import { InfoIcon, RotateCcwIcon, XIcon } from "lucide-react";

import { Col } from "@/shared/components/container";

import { getSchemaDefaultSort, type Sort } from "@/entities/nodes/object/domain/sort";
import {
  getSortableFields,
  type SortDirection,
  type SortFieldKey,
} from "@/entities/nodes/object/domain/sortable-field";
import {
  AddSort,
  AddSortPicker,
  DIRECTION_OPTIONS,
} from "@/entities/nodes/object/ui/sort/add-sort";
import { useSort } from "@/entities/nodes/object/ui/sort/use-sort";
import type { ModelSchema } from "@/entities/schema/types";

interface SortEditorProps {
  schema: ModelSchema;
}

export function SortEditor({ schema }: SortEditorProps) {
  const [sort, setSort] = useSort(schema);

  const sortableFields = getSortableFields(schema);
  const currentSort: Sort[] = sort ?? getSchemaDefaultSort(schema) ?? [];

  const addSort = (newSort: Sort) => setSort([...currentSort, newSort]);

  if (currentSort.length === 0) {
    return <AddSortPicker fields={sortableFields} onSelect={addSort} />;
  }

  const usedFields = new Set(currentSort.map((entry) => entry.field));
  const unusedFields = sortableFields.filter((field) => !usedFields.has(field.field));

  return (
    <>
      <Col className="items-start gap-1 p-1">
        <SortableList aria-label="Sort keys" items={currentSort} onReorder={setSort}>
          {(entry) => (
            <SortableItem id={entry.field} textValue={entry.field}>
              <SortRow schema={schema} sort={entry} />
            </SortableItem>
          )}
        </SortableList>

        <AddSort fields={unusedFields} onAdd={addSort} />
      </Col>

      <SortEditorFooter schema={schema} />
    </>
  );
}

interface SortEditorFooterProps {
  schema: ModelSchema;
}

function SortEditorFooter({ schema }: SortEditorFooterProps) {
  const [sort, setSort] = useSort(schema);
  const resetSort = () => setSort([]);

  return (
    <div className="border-neutral-300 border-t p-1 text-center">
      {sort === null ? (
        <div className="p-1 text-stone-400 text-xs">
          Default order · edit or add a field to customize
        </div>
      ) : (
        <Button variant="outline" size="xs" className="w-full text-stone-600" onPress={resetSort}>
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
      )}
    </div>
  );
}

interface SortRowProps {
  schema: ModelSchema;
  sort: Sort;
}

function SortRow({ schema, sort }: SortRowProps) {
  const [userSort, setSort] = useSort(schema);
  const currentSort = userSort ?? getSchemaDefaultSort(schema) ?? [];

  const fieldsUsedByOtherRows = new Set(
    currentSort.filter((entry) => entry.field !== sort.field).map((entry) => entry.field)
  );
  const availableFields = getSortableFields(schema).filter(
    (field) => !fieldsUsedByOtherRows.has(field.field)
  );

  const replaceField = (field: SortFieldKey) =>
    setSort(currentSort.map((entry) => (entry.field === sort.field ? { ...entry, field } : entry)));

  const replaceDirection = (direction: SortDirection) =>
    setSort(
      currentSort.map((entry) => (entry.field === sort.field ? { ...entry, direction } : entry))
    );

  const remove = () => setSort(currentSort.filter((entry) => entry.field !== sort.field));

  // Removing the only row while on the schema default is a no-op (it snaps back), so hide it.
  const canRemove = !(userSort === null && currentSort.length === 1);

  return (
    <>
      <Select
        aria-label="Sort field"
        value={sort.field}
        onChange={(value) => replaceField(String(value) as SortFieldKey)}
        className="min-w-0 flex-1"
      >
        <SelectTrigger size="sm" />
        <Popover>
          <Autocomplete>
            <ListBox items={availableFields} selectionMode="single">
              {(field) => (
                <ListBoxItem id={field.field} textValue={field.label}>
                  {field.label}
                </ListBoxItem>
              )}
            </ListBox>
          </Autocomplete>
        </Popover>
      </Select>

      <Select
        aria-label="Sort direction"
        value={sort.direction}
        onChange={(value) => replaceDirection(value as SortDirection)}
        className="w-32 shrink-0"
      >
        <SelectTrigger size="sm" />

        <Popover>
          <ListBox items={DIRECTION_OPTIONS} selectionMode="single">
            {(direction) => (
              <ListBoxItem textValue={direction.label}>{direction.label}</ListBoxItem>
            )}
          </ListBox>
        </Popover>
      </Select>

      {canRemove ? (
        <Button variant="ghost" size="sm" shape="square" aria-label="Remove sort" onPress={remove}>
          <XIcon />
        </Button>
      ) : (
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
      )}
    </>
  );
}
