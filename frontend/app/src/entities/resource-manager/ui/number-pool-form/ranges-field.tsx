import { Button } from "@infrahub/ui";
import { PlusIcon, Trash2Icon } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { useFieldArray, useFormContext, useFormState, useWatch } from "react-hook-form";

import { Col, Row } from "@/shared/components/container";
import { Input } from "@/shared/components/ui/input";
import { inputErrorStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";
import { formatNumberDisplay } from "@/shared/utils/number";

import {
  EMPTY_RANGE_ROW,
  type RangeRow,
  type StoredRange,
} from "@/entities/resource-manager/domain/model/number-pool-range";
import { NUMBER_POOL_RANGES_FIELD } from "@/entities/resource-manager/domain/model/pool";
import { sortStoredRanges } from "@/entities/resource-manager/domain/rules/plan-range-changes";
import {
  formatRange,
  getRangeClipHint,
  type RangeLimits,
  validateRangeRows,
} from "@/entities/resource-manager/domain/rules/validate-range-rows";

type RangeKey = "start" | "end" | "weight";
type RangeFieldName = `${typeof NUMBER_POOL_RANGES_FIELD}.${number}.${RangeKey}`;
type RangesFormValues = { [NUMBER_POOL_RANGES_FIELD]: RangeRow[] };

const WEIGHT_ORDER_NOTE =
  "The highest weight is used first. An empty weight counts as 0, and equal weights start with the lowest range.";

const RANGE_KEYS: RangeKey[] = ["start", "end", "weight"];
const RANGE_LABELS: Record<RangeKey, string> = { start: "Start", end: "End", weight: "Weight" };
const RANGE_WIDTHS: Record<RangeKey, string> = {
  start: "min-w-0 flex-1",
  end: "min-w-0 flex-1",
  weight: "w-18 shrink-0",
};

function getRangeError(rows: RangeRow[], index: number, key: RangeKey): string | true {
  const errors = validateRangeRows(rows)[index] ?? {};
  if (key === "weight") return errors.weight ?? true;
  return errors[key] ?? errors.row ?? true;
}

interface RangesFieldProps {
  limits?: RangeLimits | null;
}

export function RangesField({ limits }: RangesFieldProps) {
  const { control, register, getValues, getFieldState, trigger } =
    useFormContext<RangesFormValues>();
  const { fields, append, remove } = useFieldArray({ control, name: NUMBER_POOL_RANGES_FIELD });
  const rows = useWatch({ control, name: NUMBER_POOL_RANGES_FIELD }) ?? [];
  const formState = useFormState({ control, name: NUMBER_POOL_RANGES_FIELD });
  const [isRemovalPending, setIsRemovalPending] = useState(false);

  function revalidate(changedField?: RangeFieldName) {
    const current = getValues(NUMBER_POOL_RANGES_FIELD);
    const rowErrors = validateRangeRows(current);
    const fieldNames = current.flatMap((_, index) =>
      RANGE_KEYS.map((key) => ({
        key,
        name: `${NUMBER_POOL_RANGES_FIELD}.${index}.${key}` as const,
      })).filter(
        ({ key, name }) =>
          name === changedField ||
          getFieldState(name).invalid ||
          (key !== "weight" && !!rowErrors[index]?.row)
      )
    );
    trigger(fieldNames.map(({ name }) => name));
  }

  // Each row's validator captures its index at registration, so rows are revalidated only once they have re-registered after a removal.
  useEffect(() => {
    if (!isRemovalPending) return;
    setIsRemovalPending(false);
    revalidate();
  }, [isRemovalPending]);

  return (
    <Col>
      <RangesHeader description={`${WEIGHT_ORDER_NOTE}${describeLimits(limits)}`} />

      {fields.length > 0 && (
        <Row aria-hidden className="px-0.5 font-medium text-foreground-muted text-xs">
          {RANGE_KEYS.map((key) => (
            <span key={key} className={RANGE_WIDTHS[key]}>
              {RANGE_LABELS[key]}
            </span>
          ))}
          <span className="w-9 shrink-0" />
        </Row>
      )}

      {fields.map((field, index) => {
        // RHF mutates its errors object in place, so errors are read through the per-render form state to stay fresh under the React Compiler.
        const fieldErrors = RANGE_KEYS.map(
          (key) =>
            getFieldState(`${NUMBER_POOL_RANGES_FIELD}.${index}.${key}`, formState).error?.message
        );
        const message = fieldErrors.find(Boolean);
        const clipHint = getRangeClipHint(rows[index] ?? field, limits);
        const messageId = `range-${field.id}-message`;

        return (
          <Col key={field.id} className="gap-1">
            <Row>
              {RANGE_KEYS.map((key, keyIndex) => {
                const name: RangeFieldName = `${NUMBER_POOL_RANGES_FIELD}.${index}.${key}`;
                const hasError = !!fieldErrors[keyIndex];

                return (
                  <Input
                    key={key}
                    aria-label={`${RANGE_LABELS[key]}, range ${index + 1}`}
                    inputMode="numeric"
                    placeholder={key === "weight" ? "0" : undefined}
                    aria-invalid={hasError}
                    aria-describedby={message || clipHint ? messageId : undefined}
                    className={classNames(
                      "h-9 min-h-0 rounded-lg px-2 tabular-nums",
                      RANGE_WIDTHS[key],
                      hasError && inputErrorStyle
                    )}
                    {...register(name, {
                      validate: (_value, values) =>
                        getRangeError(values[NUMBER_POOL_RANGES_FIELD], index, key),
                      onBlur: () => revalidate(name),
                      onChange: () => {
                        if (formState.isSubmitted || getFieldState(name).isTouched)
                          revalidate(name);
                      },
                    })}
                  />
                );
              })}
              <Button
                variant="ghost"
                shape="square"
                size="md"
                aria-label={`Remove range ${index + 1}`}
                className="text-foreground-muted"
                onPress={() => {
                  remove(index);
                  setIsRemovalPending(true);
                }}
              >
                <Trash2Icon />
              </Button>
            </Row>

            {message && (
              <p id={messageId} role="alert" className="text-danger text-xs">
                {message}
              </p>
            )}
            {!message && clipHint && (
              <p id={messageId} className="text-warning text-xs">
                {clipHint}
              </p>
            )}
          </Col>
        );
      })}

      {fields.length === 0 && (
        <p className="rounded-lg border border-dashed px-3 py-2.5 text-foreground-muted text-sm">
          No ranges. The pool can't hand out numbers until you add one.
        </p>
      )}

      <Button
        variant="ghost"
        size="sm"
        className="self-start"
        onPress={() => append({ ...EMPTY_RANGE_ROW })}
      >
        <PlusIcon />
        Add range
      </Button>
    </Col>
  );
}

interface ReadOnlyRangesFieldProps {
  ranges: StoredRange[];
}

export function ReadOnlyRangesField({ ranges }: ReadOnlyRangesFieldProps) {
  return (
    <Col>
      <RangesHeader description="These ranges come from the schema. To change them, update the schema on the default branch." />

      {ranges.length === 0 ? (
        <p className="text-foreground-muted text-sm">No ranges.</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {sortStoredRanges(ranges).map((range) => (
            <li key={range.id} className="flex gap-2 text-sm tabular-nums">
              <span>{formatRange(range.start, range.end)}</span>
              {range.weight !== null && (
                <span className="text-foreground-muted">
                  Weight {formatNumberDisplay(range.weight)}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </Col>
  );
}

function describeLimits(limits?: RangeLimits | null): string {
  const { attribute, min, max } = limits ?? {};
  if (min == null || max == null) return "";
  return ` ${attribute} accepts ${formatRange(BigInt(min), BigInt(max))}.`;
}

function RangesHeader({ description }: { description: ReactNode }) {
  return (
    <Col className="gap-0.5">
      <h3 className="font-medium text-sm">Ranges</h3>
      <p className="text-pretty text-foreground-muted text-xs">{description}</p>
    </Col>
  );
}
