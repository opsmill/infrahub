import { Autocomplete, Button, ListBox, Popover, Select, SelectItem } from "@infrahub/ui";
import { PlusIcon, XIcon } from "lucide-react";
import React from "react";
import { Group, SelectValue, Tag, TagGroup, TagList } from "react-aria-components";

import { Col, Row } from "@/shared/components/container";
import { classNames } from "@/shared/utils/common";

import { canNumberPoolBeScopedBy } from "@/entities/resource-manager/domain/rules/can-number-pool-be-scoped-by";
import { canNumberPoolHaveAllocationScope } from "@/entities/resource-manager/domain/rules/can-number-pool-have-allocation-scope";
import type {
  AttributeSchema,
  FieldSchema,
  ModelSchema,
} from "@/entities/schema/domain/model/schema";
import { FieldSchemaIcon } from "@/entities/schema/ui/field-schema-icon";

const getFieldLabel = (field: FieldSchema) => field.label ?? field.name;

function getAllocationScopeItems(schema: ModelSchema, attribute: AttributeSchema) {
  return [...(schema.attributes ?? []), ...(schema.relationships ?? [])]
    .filter((field) => field.name !== attribute.name && canNumberPoolBeScopedBy(field))
    .sort((a, b) => getFieldLabel(a).localeCompare(getFieldLabel(b)))
    .map((field) => ({ id: field.name, field }));
}

type AllocationScopeItem = ReturnType<typeof getAllocationScopeItems>[number];

function getAddLabel(attribute: AttributeSchema, hasItems: boolean, isEmpty: boolean): string {
  if (!canNumberPoolHaveAllocationScope(attribute)) return "No scope";
  if (!hasItems) return "No relationship or attribute eligible";
  return isEmpty ? "Add a relationship or attribute" : "Add another";
}

interface AllocationScopeProps {
  schema: ModelSchema;
  attribute: AttributeSchema;
  value: ReadonlyArray<string>;
}

interface EditableAllocationScopeProps extends AllocationScopeProps {
  onChange: (names: Array<string>) => void;
  isInvalid?: boolean;
}

export type NumberPoolAllocationScopeSelectProps =
  | (EditableAllocationScopeProps & { isReadOnly?: false })
  | (AllocationScopeProps & { isReadOnly: true });

export function NumberPoolAllocationScopeSelect(props: NumberPoolAllocationScopeSelectProps) {
  if (props.isReadOnly) {
    return <ReadOnlyAllocationScope schema={props.schema} value={props.value} />;
  }

  return <EditableAllocationScope {...props} />;
}

function ReadOnlyAllocationScope({
  schema,
  value,
}: Pick<AllocationScopeProps, "schema" | "value">) {
  if (value.length === 0) return <span className="text-foreground-muted">No scope</span>;

  const fields = [...(schema.attributes ?? []), ...(schema.relationships ?? [])];

  return (
    <ul aria-label="Scoped by" className="flex min-w-0 flex-col">
      {value.map((name) => {
        const field = fields.find((candidate) => candidate.name === name);
        const label = field ? getFieldLabel(field) : name;

        return (
          <li key={name} className="flex h-7 min-w-0 items-center gap-1.5">
            <span className="min-w-0 truncate font-medium" title={label}>
              {label}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function EditableAllocationScope({
  schema,
  attribute,
  value,
  onChange,
  isInvalid,
}: EditableAllocationScopeProps) {
  const items = getAllocationScopeItems(schema, attribute);
  const canHaveAllocationScope = canNumberPoolHaveAllocationScope(attribute);
  const isDisabled = !canHaveAllocationScope || items.length === 0;
  const isEmpty = !items.some(({ id }) => value.includes(id));
  const isEveryFieldPicked = items.length > 0 && items.every(({ id }) => value.includes(id));
  const fieldRef = React.useRef<HTMLDivElement>(null);
  const addButtonRef = React.useRef<HTMLButtonElement>(null);
  const addLabelId = React.useId();

  const remove = (names: Set<React.Key>) => {
    const next = value.filter((name) => !names.has(name));
    onChange(next);
    // The tag list unmounts once empty, so focus would otherwise fall back to the page.
    if (next.length === 0) addButtonRef.current?.focus();
  };

  return (
    <Col className="gap-1">
      <Select
        selectionMode="multiple"
        aria-label="Scoped by"
        value={value}
        onChange={(names) => onChange(names.map(String))}
        isDisabled={isDisabled}
        isInvalid={isInvalid}
      >
        <Group
          ref={fieldRef}
          isDisabled={isDisabled}
          isInvalid={isInvalid}
          className={classNames(
            "flex min-h-8 w-full flex-col rounded-lg border border-border-strong bg-input p-0.5 shadow-input data-disabled:cursor-not-allowed data-invalid:border-danger data-disabled:opacity-60",
            isEmpty && "border-dashed"
          )}
        >
          {!isEmpty && (
            <SelectValue<AllocationScopeItem> className="flex min-w-0 flex-col">
              {({ selectedItems }) => (
                <TagGroup aria-label="Scoped by" className="min-w-0" onRemove={remove}>
                  <TagList
                    items={selectedItems.filter((item) => item != null)}
                    className="flex min-w-0 flex-col"
                  >
                    {({ id, field }) => <PickedField id={id} field={field} />}
                  </TagList>
                </TagGroup>
              )}
            </SelectValue>
          )}
          {!isEveryFieldPicked && (
            <Button
              ref={addButtonRef}
              slot={undefined} // Opting back into slots lets the select use this button as its trigger.
              aria-labelledby={addLabelId} // Otherwise the select would add the picked fields to the button's name.
              variant="ghost"
              size="xs"
              className="w-full justify-start gap-1.5 px-1.5 text-foreground-muted"
            >
              {!isDisabled && <PlusIcon />}
              <span id={addLabelId} className="truncate">
                {getAddLabel(attribute, items.length > 0, isEmpty)}
              </span>
            </Button>
          )}
        </Group>

        <Popover placement="bottom end" width="min-trigger" triggerRef={fieldRef}>
          <Autocomplete>
            <ListBox
              selectionMode="multiple"
              items={items}
              className="max-h-72"
              emptyMessage="No matching relationship or attribute"
            >
              {({ field }) => (
                <SelectItem textValue={getFieldLabel(field)}>
                  <Row>
                    <FieldSchemaIcon fieldSchema={field} />
                    <span className="min-w-0 grow truncate">{getFieldLabel(field)}</span>
                  </Row>
                </SelectItem>
              )}
            </ListBox>
          </Autocomplete>
        </Popover>
      </Select>

      {!canHaveAllocationScope && (
        <p className="text-pretty text-subtle-muted text-xs">
          {getFieldLabel(attribute)} is unique across all nodes, so it cannot have a scope.
        </p>
      )}
    </Col>
  );
}

function PickedField({ id, field }: AllocationScopeItem) {
  const label = getFieldLabel(field);

  return (
    <Tag
      id={id}
      textValue={label}
      className="flex h-7 min-w-0 items-center gap-1.5 rounded-md pr-0.5 pl-1.5 text-sm outline-none hover:bg-highlight data-focus-visible:bg-highlight"
    >
      <span className="min-w-0 grow truncate font-medium" title={label}>
        {label}
      </span>
      <Button
        slot="remove"
        excludeFromTabOrder // Backspace and Delete remove the focused field, so the button needs no Tab stop.
        variant="ghost"
        shape="square"
        size="xxs"
        className="shrink-0 text-foreground-muted"
      >
        <XIcon />
      </Button>
    </Tag>
  );
}
