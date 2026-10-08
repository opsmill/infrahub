// PROTO number-pool — the pool edit sheet with the rows range editor. Delete with the prototype.
import { Button, Sheet } from "@infrahub/ui";
import { PlusIcon, Trash2Icon, XIcon } from "lucide-react";
import React from "react";
import { toast } from "react-toastify";

import { SlideOverTitle } from "@/shared/components/display/slide-over";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Input } from "@/shared/components/ui/input";
import { inputErrorStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import type { Dataset } from "./data";
import { sortRanges } from "./data";
import { attrCode } from "./header";
import { fmt } from "./parts";
import { findKind, ScopeField, WarningNote } from "./scope-field";

export const EditPoolContext = React.createContext<(() => void) | null>(null);

export type Draft = { key: string; start: string; end: string; weight: string };
type RowErrors = { start?: string; end?: string; weight?: string; row?: string };

let nextKey = 0;
export const newKey = () => `n${nextKey++}`;

const toInt = (value: string) => {
  const clean = value.replace(/[,_\s]/g, "");
  return /^\d+$/.test(clean) ? Number(clean) : null;
};

const label = (start: number, end: number) => `${fmt.format(start)} – ${fmt.format(end)}`;

export function validate(drafts: Draft[]): Record<string, RowErrors> {
  const errors: Record<string, RowErrors> = {};
  const bounds: { key: string; start: number; end: number }[] = [];
  for (const d of drafts) {
    const e: RowErrors = {};
    const start = toInt(d.start);
    const end = toInt(d.end);
    const weight = toInt(d.weight);
    if (d.start.trim() === "") e.start = "Required";
    else if (start === null) e.start = "Whole number";
    if (d.end.trim() === "") e.end = "Required";
    else if (end === null) e.end = "Whole number";
    if (d.weight.trim() !== "" && weight === null) e.weight = "0 or more";
    if (start !== null && end !== null) {
      if (start > end) e.row = "Start must not be greater than end";
      else bounds.push({ key: d.key, start, end });
    }
    if (Object.keys(e).length) errors[d.key] = e;
  }
  for (let i = 0; i < bounds.length; i++) {
    for (let j = i + 1; j < bounds.length; j++) {
      const a = bounds[i]!;
      const b = bounds[j]!;
      if (a.start <= b.end && b.start <= a.end) {
        errors[a.key] = { ...errors[a.key], row: `Overlaps ${label(b.start, b.end)}` };
        errors[b.key] = { ...errors[b.key], row: `Overlaps ${label(a.start, a.end)}` };
      }
    }
  }
  return errors;
}

function sortDrafts(drafts: Draft[]) {
  return [...drafts].sort(
    (a, b) =>
      (toInt(b.weight) ?? 0) - (toInt(a.weight) ?? 0) ||
      (toInt(a.start) ?? Infinity) - (toInt(b.start) ?? Infinity)
  );
}

function initialDrafts(dataset: Dataset): Draft[] {
  return sortRanges(dataset.ranges).map((r) => ({
    key: r.id,
    start: String(r.start),
    end: String(r.end),
    weight: r.weight === null ? "" : String(r.weight),
  }));
}

const numberInput = "h-9 min-h-0 rounded-lg px-2 tabular-nums";

export function ErrorText({ id, children }: { id?: string; children?: string }) {
  if (!children) return null;
  return (
    <p id={id} className="text-danger text-xs">
      {children}
    </p>
  );
}

// re-sorting while someone types would move the row under their cursor, so it waits until focus leaves the row
function useSortOnRowBlur(setDrafts: React.Dispatch<React.SetStateAction<Draft[]>>) {
  return (e: React.FocusEvent<HTMLElement>) => {
    if (e.currentTarget.contains(e.relatedTarget as Node | null)) return;
    setDrafts((d) => sortDrafts(d));
  };
}

type AttributeLimits = { attribute: string; min: number; max: number };

// the backend clips a range to the attribute's limits instead of refusing it
function clipHint(d: Draft, limits?: AttributeLimits) {
  if (!limits) return null;
  const start = toInt(d.start);
  const end = toInt(d.end);
  if (start === null || end === null || start > end) return null;
  if (start >= limits.min && end <= limits.max) return null;
  if (end < limits.min || start > limits.max) {
    return `Outside the ${limits.attribute} limits, so no number can come from it`;
  }
  return `Clipped to ${label(Math.max(start, limits.min), Math.min(end, limits.max))} by the ${limits.attribute} limits`;
}

export function RangesSectionHeader({ limits }: { limits?: AttributeLimits }) {
  return (
    <div className="flex flex-col gap-0.5">
      <h3 className="font-medium text-sm">Ranges</h3>
      <p className="text-pretty text-foreground-muted text-xs">
        The highest weight is used first. An empty weight counts as 0, and equal weights start with
        the lowest range.
        {limits && ` ${limits.attribute} accepts ${label(limits.min, limits.max)}.`}
      </p>
    </div>
  );
}

export function RowsEditor({
  drafts,
  setDrafts,
  errors,
  limits,
}: {
  drafts: Draft[];
  setDrafts: React.Dispatch<React.SetStateAction<Draft[]>>;
  errors: Record<string, RowErrors>;
  limits?: AttributeLimits;
}) {
  const onRowBlur = useSortOnRowBlur(setDrafts);
  const update = (key: string, field: keyof Draft, value: string) =>
    setDrafts((d) => d.map((x) => (x.key === key ? { ...x, [field]: value } : x)));
  const grid = "grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_4.5rem_2rem] items-start gap-2";

  return (
    <div className="flex flex-col gap-2">
      {drafts.length > 0 && (
        <div className={classNames(grid, "px-0.5 font-medium text-foreground-muted text-xs")}>
          <span>Start</span>
          <span>End</span>
          <span>Weight</span>
          <span />
        </div>
      )}
      {drafts.map((d) => {
        const e = errors[d.key] ?? {};
        const errorId = `range-error-${d.key}`;
        const message = e.row ?? e.start ?? e.end ?? e.weight;
        return (
          <div key={d.key} className="flex flex-col gap-1" onBlur={onRowBlur}>
            <div className={grid}>
              <Input
                aria-label="Start"
                inputMode="numeric"
                value={d.start}
                onChange={(ev) => update(d.key, "start", ev.target.value)}
                aria-invalid={!!(e.start || e.row)}
                aria-describedby={message ? errorId : undefined}
                className={classNames(numberInput, (e.start || e.row) && inputErrorStyle)}
              />
              <Input
                aria-label="End"
                inputMode="numeric"
                value={d.end}
                onChange={(ev) => update(d.key, "end", ev.target.value)}
                aria-invalid={!!(e.end || e.row)}
                aria-describedby={message ? errorId : undefined}
                className={classNames(numberInput, (e.end || e.row) && inputErrorStyle)}
              />
              <Input
                aria-label="Weight"
                inputMode="numeric"
                placeholder="0"
                value={d.weight}
                onChange={(ev) => update(d.key, "weight", ev.target.value)}
                aria-invalid={!!e.weight}
                aria-describedby={message ? errorId : undefined}
                className={classNames(numberInput, e.weight && inputErrorStyle)}
              />
              <Button
                variant="ghost"
                shape="square"
                size="md"
                aria-label="Remove range"
                onPress={() => setDrafts((x) => x.filter((r) => r.key !== d.key))}
                className="text-foreground-muted"
              >
                <Trash2Icon />
              </Button>
            </div>
            {message ? (
              <ErrorText id={errorId}>{message}</ErrorText>
            ) : (
              clipHint(d, limits) && (
                <p id={errorId} className="text-warning text-xs">
                  {clipHint(d, limits)}
                </p>
              )
            )}
          </div>
        );
      })}
      {drafts.length === 0 && (
        <p className="rounded-lg border border-dashed px-3 py-2.5 text-foreground-muted text-sm">
          No ranges. The pool can't hand out numbers until you add one.
        </p>
      )}
      <Button
        variant="ghost"
        size="sm"
        className="self-start"
        onPress={() => setDrafts((d) => [...d, { key: newKey(), start: "", end: "", weight: "" }])}
      >
        <PlusIcon />
        Add range
      </Button>
    </div>
  );
}

export function EditPoolSheet({
  dataset,
  isOpen,
  onOpenChange,
}: {
  dataset: Dataset;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { schema } = useSchema("CoreNumberPool");
  const { pool } = dataset;
  const [name, setName] = React.useState(pool.name);
  const [description, setDescription] = React.useState(pool.description);
  const [drafts, setDrafts] = React.useState(() => initialDrafts(dataset));
  const originalScope = pool.scopedBy.map((r) => r.name);
  const [scope, setScope] = React.useState(originalScope);
  const kindSchema = findKind(pool.targetKind);
  const scopeChanged = scope.join("|") !== originalScope.join("|");
  const hasNumbers = dataset.scopes
    ? dataset.scopes.length > 0
    : !!dataset.implicitScope &&
      dataset.implicitScope.usage.defaultUsed + dataset.implicitScope.usage.branchUsed > 0;
  const limits = { attribute: pool.targetAttribute, ...pool.attributeLimits };
  const errors = validate(drafts);
  const hasErrors = Object.keys(errors).length > 0 || name.trim() === "";

  return (
    <Sheet
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      aria-label={`Edit ${pool.name}`}
      className="flex flex-col p-0"
    >
      <div className="flex flex-1 flex-col gap-5 p-3">
        {schema && (
          <SlideOverTitle
            schema={schema}
            currentObjectLabel={pool.name}
            title={`Edit ${pool.name}`}
          />
        )}

        <label className="flex flex-col gap-1.5">
          <span className="font-medium text-sm">Name</span>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            aria-invalid={name.trim() === ""}
            className={classNames(name.trim() === "" && inputErrorStyle)}
          />
          {name.trim() === "" && <ErrorText>Required</ErrorText>}
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="font-medium text-sm">Description</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full rounded-xl border border-input-border bg-input p-2 text-sm shadow-input focus-visible:border-ring focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring-halo"
          />
        </label>

        <div className="flex flex-col gap-1.5">
          <span className="font-medium text-sm">What it allocates</span>
          <div className="grid grid-cols-[5rem_minmax(0,1fr)] items-center gap-x-2 gap-y-2.5 rounded-xl border bg-card p-2.5 text-sm">
            <span className="text-foreground-muted">Node</span>
            <span className="font-medium">{pool.targetKind}</span>
            <span className="text-foreground-muted">Attribute</span>
            <span>
              <code className={attrCode}>{pool.targetAttribute}</code>
            </span>
            <span className="self-start pt-1.5 text-foreground-muted">Scoped by</span>
            <ScopeField schema={kindSchema} scope={scope} setScope={setScope} />
          </div>
          <p className="text-foreground-muted text-xs">
            The kind and attribute are set when the pool is created.
          </p>
          {scopeChanged && hasNumbers && (
            <WarningNote>
              Changing the scope recounts which numbers are taken; no number is reassigned. Adding a
              field gives each new combination its own sequence, so numbers can be reused. Removing
              a field merges sequences, so a number used in one of them counts as taken in all of
              them.
            </WarningNote>
          )}
        </div>

        <section className="flex flex-col gap-2">
          <RangesSectionHeader limits={limits} />
          <RowsEditor drafts={drafts} setDrafts={setDrafts} errors={errors} limits={limits} />
          {drafts.length === 0 && hasNumbers && (
            <WarningNote>
              Without a range the pool can't hand out numbers. Numbers already assigned stay
              assigned.
            </WarningNote>
          )}
        </section>
      </div>

      <div className="sticky bottom-0 flex justify-end gap-2 border-t bg-secondary p-3">
        <Button variant="outline" onPress={() => onOpenChange(false)}>
          <XIcon />
          Cancel
        </Button>
        <Button
          variant="primary"
          isDisabled={hasErrors}
          onPress={() => {
            toast(
              <Alert
                type={ALERT_TYPES.SUCCESS}
                message="Number pool updated (prototype, nothing saved)"
              />
            );
            onOpenChange(false);
          }}
        >
          Save changes
        </Button>
      </div>
    </Sheet>
  );
}
