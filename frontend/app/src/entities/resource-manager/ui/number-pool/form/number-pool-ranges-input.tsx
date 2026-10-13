import { Button } from "@infrahub/ui";
import { PlusIcon, Trash2Icon } from "lucide-react";
import React from "react";
import { useController, useFieldArray, useFormContext } from "react-hook-form";

import { Col, Row } from "@/shared/components/container";
import { usePreventScrollOnNumberInput } from "@/shared/components/form/fields/usePreventScrollOnNumber";
import { Input } from "@/shared/components/ui/input";
import { inputErrorStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { findOverlappingRanges } from "@/entities/resource-manager/domain/rules/find-overlapping-ranges";
import type { NumberPoolFormData } from "@/entities/resource-manager/ui/number-pool/form/number-pool-form";

export type NumberPoolRangeRow = NumberPoolFormData["ranges"][number];

// A number input reports an empty field as NaN.
export function validateRangeBound(value: number): string | true {
  if (Number.isNaN(value)) return "Required";
  if (!Number.isInteger(value) || value < 0) return "Whole number";
  if (!Number.isSafeInteger(value)) return "Too large";
  return true;
}

export function validateRangeWeight(value: number | null): string | true {
  return value === null || validateRangeBound(value);
}

export function validateRangeOrder(
  rows: ReadonlyArray<NumberPoolRangeRow>,
  index: number
): string | true {
  const row = rows[index];
  return row && row.start > row.end ? "End is below start" : true;
}

export function validateRangeOverlap(
  rows: ReadonlyArray<NumberPoolRangeRow>,
  index: number
): string | true {
  // An inverted row is reported by its own order check, so it takes no part in overlaps.
  const completeRows = rows
    .map(({ start, end }, key) => ({ key, start, end }))
    .filter(({ start, end }) => !Number.isNaN(start) && !Number.isNaN(end) && start <= end);
  const others = findOverlappingRanges(completeRows).get(index);
  if (!others) return true;

  return `Overlaps ${others.map(({ start, end }) => `${start} – ${end}`).join(", ")}`;
}

const numberInputClassName = "h-9 min-h-0 rounded-lg px-2 tabular-nums";
const boundClassName = "min-w-0 flex-1";
const weightClassName = "w-18 shrink-0";
const removeColumnClassName = "w-9 shrink-0";

export const createRangeRow = (): NumberPoolRangeRow => ({
  start: Number.NaN,
  end: Number.NaN,
  allocation_weight: null,
});

interface NumberPoolRangeRowInputProps {
  index: number;
  rowCount: number;
  onRemove: () => void;
}

const getRangeBoundNames = (rowCount: number) =>
  Array.from({ length: rowCount }, (_, i) => [
    `ranges.${i}.start` as const,
    `ranges.${i}.end` as const,
  ]).flat();

function NumberPoolRangeRowInput({ index, rowCount, onRemove }: NumberPoolRangeRowInputProps) {
  // An edit to one row can create or clear an overlap with any other row.
  const boundsOfAllRows = getRangeBoundNames(rowCount);
  const order = (_: number, values: NumberPoolFormData) => validateRangeOrder(values.ranges, index);
  const overlap = (_: number, values: NumberPoolFormData) =>
    validateRangeOverlap(values.ranges, index);

  const start = useController<NumberPoolFormData, `ranges.${number}.start`>({
    name: `ranges.${index}.start`,
    rules: { validate: { wholeNumber: validateRangeBound, overlap }, deps: boundsOfAllRows },
  });
  const end = useController<NumberPoolFormData, `ranges.${number}.end`>({
    name: `ranges.${index}.end`,
    rules: {
      validate: { wholeNumber: validateRangeBound, order, overlap },
      deps: boundsOfAllRows,
    },
  });
  const weight = useController<NumberPoolFormData, `ranges.${number}.allocation_weight`>({
    name: `ranges.${index}.allocation_weight`,
    rules: { validate: validateRangeWeight },
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
      value: Number.isNaN(start.field.value) ? "" : start.field.value,
      onChange: (value: number) => start.field.onChange(value),
      onBlur: start.field.onBlur,
      className: boundClassName,
    },
    {
      label: `End of ${position}`,
      ref: endRef,
      fieldState: end.fieldState,
      value: Number.isNaN(end.field.value) ? "" : end.field.value,
      onChange: (value: number) => end.field.onChange(value),
      onBlur: end.field.onBlur,
      className: boundClassName,
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
              min={0}
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
