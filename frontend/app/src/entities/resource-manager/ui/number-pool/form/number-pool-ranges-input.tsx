import { Button } from "@infrahub/ui";
import { PlusIcon, Trash2Icon } from "lucide-react";
import React from "react";
import { useController, useFieldArray, useFormContext, useWatch } from "react-hook-form";

import { Col, Row } from "@/shared/components/container";
import { usePreventScrollOnNumberInput } from "@/shared/components/form/fields/usePreventScrollOnNumber";
import { Input } from "@/shared/components/ui/input";
import { inputErrorStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { findOverlappingRanges } from "@/entities/resource-manager/domain/rules/find-overlapping-ranges";
import type { NumberPoolFormData } from "@/entities/resource-manager/ui/number-pool/form/number-pool-form";
import type { NumberAttributeParameters } from "@/entities/schema/domain/model/schema";
import { validateNumberAttribute } from "@/entities/schema/domain/rules/validation/validate-number-attribute";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export type NumberPoolRangeRow = NumberPoolFormData["ranges"][number];

export function validateRangeBound(value: number | null): string | true {
  if (value === null) return true;
  if (!Number.isInteger(value)) return "Whole number";
  if (!Number.isSafeInteger(value)) return value > 0 ? "Too large" : "Too small";
  return true;
}

// The server reads a range without a start as starting at 1 and a range without an end as ending at the largest number it can store.
const resolveRangeBounds = ({ start, end }: Pick<NumberPoolRangeRow, "start" | "end">) => ({
  start: start ?? 1,
  end: end ?? Number.POSITIVE_INFINITY,
});

const formatRangeBound = (value: number) =>
  value === Number.POSITIVE_INFINITY ? "MAX" : String(value);

export function validateRangeOrder(
  rows: ReadonlyArray<NumberPoolRangeRow>,
  index: number
): string | true {
  const row = rows[index];
  if (!row) return true;
  const { start, end } = resolveRangeBounds(row);
  return start > end ? "End is below start" : true;
}

export function validateRangeOverlap(
  rows: ReadonlyArray<NumberPoolRangeRow>,
  index: number
): string | true {
  // An inverted row is reported by its own order check, so it takes no part in overlaps.
  const orderedRows = rows
    .map((row, key) => ({ key, ...resolveRangeBounds(row) }))
    .filter(({ start, end }) => start <= end);
  const others = findOverlappingRanges(orderedRows).get(index);
  if (!others) return true;

  return `Overlaps ${others
    .map(({ start, end }) => `${formatRangeBound(start)} – ${formatRangeBound(end)}`)
    .join(", ")}`;
}

const numberInputClassName = "h-9 min-h-0 rounded-lg px-2 tabular-nums";
const boundClassName = "min-w-0 flex-1";
const weightClassName = "w-18 shrink-0";
const removeColumnClassName = "w-9 shrink-0";

export const createRangeRow = (): NumberPoolRangeRow => ({
  start: null,
  end: null,
  allocation_weight: null,
});

interface NumberPoolRangeRowInputProps {
  index: number;
  rowCount: number;
  attributeParameters?: NumberAttributeParameters;
  onRemove: () => void;
}

const getRangeBoundNames = (rowCount: number) =>
  Array.from({ length: rowCount }, (_, i) => [
    `ranges.${i}.start` as const,
    `ranges.${i}.end` as const,
  ]).flat();

function NumberPoolRangeRowInput({
  index,
  rowCount,
  attributeParameters,
  onRemove,
}: NumberPoolRangeRowInputProps) {
  // An edit to one row can create or clear an overlap with any other row.
  const boundsOfAllRows = getRangeBoundNames(rowCount);
  const order = (_: number | null, values: NumberPoolFormData) =>
    validateRangeOrder(values.ranges, index);
  const overlap = (_: number | null, values: NumberPoolFormData) =>
    validateRangeOverlap(values.ranges, index);
  const withinLimits = (value: number | null) => {
    const validation = validateNumberAttribute(
      { min: attributeParameters?.min_value, max: attributeParameters?.max_value },
      value
    );
    return validation.success || validation.error;
  };

  const start = useController<NumberPoolFormData, `ranges.${number}.start`>({
    name: `ranges.${index}.start`,
    rules: {
      validate: { wholeNumber: validateRangeBound, withinLimits, overlap },
      deps: boundsOfAllRows,
    },
  });
  const end = useController<NumberPoolFormData, `ranges.${number}.end`>({
    name: `ranges.${index}.end`,
    rules: {
      validate: { wholeNumber: validateRangeBound, withinLimits, order, overlap },
      deps: boundsOfAllRows,
    },
  });
  const weight = useController<NumberPoolFormData, `ranges.${number}.allocation_weight`>({
    name: `ranges.${index}.allocation_weight`,
    rules: { validate: validateRangeBound },
  });
  const startRef = usePreventScrollOnNumberInput();
  const endRef = usePreventScrollOnNumberInput();
  const weightRef = usePreventScrollOnNumberInput();

  const message =
    start.fieldState.error?.message ??
    end.fieldState.error?.message ??
    weight.fieldState.error?.message;
  const messageId = React.useId();
  const position = `range ${index + 1}`;
  const inputs = [
    {
      label: `Start of ${position}`,
      ref: startRef,
      fieldState: start.fieldState,
      value: start.field.value ?? "",
      onChange: (value: number) => start.field.onChange(Number.isNaN(value) ? null : value),
      onBlur: start.field.onBlur,
      className: boundClassName,
      placeholder: "MIN",
    },
    {
      label: `End of ${position}`,
      ref: endRef,
      fieldState: end.fieldState,
      value: end.field.value ?? "",
      onChange: (value: number) => end.field.onChange(Number.isNaN(value) ? null : value),
      onBlur: end.field.onBlur,
      className: boundClassName,
      placeholder: "MAX",
    },
    {
      label: `Weight of ${position}`,
      ref: weightRef,
      fieldState: weight.fieldState,
      value: weight.field.value ?? "",
      onChange: (value: number) => weight.field.onChange(Number.isNaN(value) ? null : value),
      onBlur: weight.field.onBlur,
      className: weightClassName,
      placeholder: "0",
    },
  ];

  return (
    <Col className="gap-1">
      <Row className="items-start">
        {inputs.map(
          ({ label, ref, fieldState, value, onChange, onBlur, className, placeholder }) => (
            <Input
              key={label}
              ref={ref}
              type="number"
              step={1}
              aria-label={label}
              placeholder={placeholder}
              value={value}
              onChange={(event) => onChange(event.target.valueAsNumber)}
              onBlur={onBlur}
              aria-invalid={fieldState.invalid}
              aria-describedby={message ? messageId : undefined}
              className={classNames(
                numberInputClassName,
                className,
                fieldState.invalid && inputErrorStyle
              )}
            />
          )
        )}
        <Button
          variant="ghost"
          shape="square"
          size="md"
          aria-label={`Remove ${position}`}
          onPress={onRemove}
          className={classNames(removeColumnClassName, "text-foreground-muted")}
        >
          <Trash2Icon />
        </Button>
      </Row>
      {message && (
        <p id={messageId} className="text-danger text-xs">
          {message}
        </p>
      )}
    </Col>
  );
}

export function NumberPoolRangesInput() {
  const { control, formState, trigger } = useFormContext<NumberPoolFormData>();
  const { fields, append, remove } = useFieldArray({ control, name: "ranges" });
  const [nodeKind, nodeAttribute] = useWatch({
    control,
    name: ["node.value", "node_attribute.value"],
  });
  const { schema } = useSchema(nodeKind);
  const attributeParameters = schema?.attributes?.find(({ name }) => name === nodeAttribute)
    ?.parameters as NumberAttributeParameters | undefined;

  const removeRow = (index: number) => {
    remove(index);
    // Removing a row can clear another row's overlap, and a row only re-renders on errors under its own field names.
    if (formState.isSubmitted) trigger(getRangeBoundNames(fields.length - 1));
  };

  return (
    <Col>
      <Col className="gap-0.5">
        <h3 className="font-medium text-sm">Ranges</h3>
        <p className="text-foreground-muted text-xs">
          Highest weight is used first. Ranges with equal weight are used from the lowest start.
        </p>
      </Col>

      {fields.length > 0 && (
        <Row className="px-0.5 font-medium text-foreground-muted text-xs">
          <span className={boundClassName}>Start</span>
          <span className={boundClassName}>End</span>
          <span className={weightClassName}>Weight</span>
          <span className={removeColumnClassName} />
        </Row>
      )}

      {fields.map((field, index) => (
        <NumberPoolRangeRowInput
          key={field.id}
          index={index}
          rowCount={fields.length}
          attributeParameters={attributeParameters}
          onRemove={() => removeRow(index)}
        />
      ))}

      {fields.length === 0 && (
        <p className="rounded-lg border border-dashed px-3 py-2.5 text-foreground-muted text-sm">
          No ranges. The pool can't hand out numbers until you add one.
        </p>
      )}

      <Button
        variant="ghost"
        size="sm"
        className="self-start"
        onPress={() => append(createRangeRow())}
      >
        <PlusIcon />
        Add range
      </Button>
    </Col>
  );
}
