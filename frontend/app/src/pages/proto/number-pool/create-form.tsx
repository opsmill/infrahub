// PROTO number-pool — the create sheet: kind → number attribute → scope, then ranges. Delete with the prototype.
import {
  Autocomplete,
  Button,
  ListBox,
  Popover,
  Select,
  SelectItem,
  SelectTrigger,
  Sheet,
} from "@infrahub/ui";
import React from "react";
import { toast } from "react-toastify";

import { SlideOverTitle } from "@/shared/components/display/slide-over";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Input } from "@/shared/components/ui/input";
import { inputErrorStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import { type Draft, ErrorText, newKey, RangesSectionHeader, RowsEditor, validate } from "./editor";
import { findKind, KINDS, type KindSchema, ScopeField, WarningNote } from "./scope-field";

function KindSelect({
  kind,
  onChange,
  className,
}: {
  kind: string | null;
  onChange: (kind: string | null) => void;
  className?: string;
}) {
  return (
    <Select
      aria-label="Node"
      placeholder="Select a node"
      value={kind}
      onChange={(k) => onChange(k === null ? null : String(k))}
      className={className}
    >
      <SelectTrigger size="sm" />
      <Popover placement="bottom start" className="min-w-64">
        <Autocomplete>
          <ListBox
            selectionMode="single"
            items={KINDS.map((k) => ({ id: k.kind, ...k }))}
            className="max-h-72"
          >
            {(k) => (
              <SelectItem textValue={k.kind}>
                <span className="flex w-full items-baseline gap-2">
                  <span className="min-w-0 flex-1 truncate">{k.kind}</span>
                  <span className="in-[button]:hidden shrink-0 text-foreground-muted text-xs">
                    {k.label}
                  </span>
                </span>
              </SelectItem>
            )}
          </ListBox>
        </Autocomplete>
      </Popover>
    </Select>
  );
}

function AttributeSelect({
  schema,
  attribute,
  onChange,
}: {
  schema: KindSchema | null;
  attribute: string | null;
  onChange: (attribute: string | null) => void;
}) {
  const items = (schema?.numberAttributes ?? []).map((a) => ({ id: a.name, ...a }));
  return (
    <Select
      aria-label="Node attribute"
      placeholder={schema ? "Select an attribute" : "Select a node first"}
      isDisabled={!schema}
      value={attribute}
      onChange={(a) => onChange(a === null ? null : String(a))}
    >
      <SelectTrigger size="sm" />
      <Popover placement="bottom start" className="min-w-56">
        <ListBox selectionMode="single" items={items} className="max-h-72">
          {(a) => (
            <SelectItem textValue={a.name}>
              <span className="flex w-full items-baseline gap-2">
                <span className="min-w-0 flex-1 truncate font-mono text-xs">{a.name}</span>
                {a.unique && (
                  <span className="in-[button]:hidden shrink-0 text-foreground-muted text-xs">
                    Unique
                  </span>
                )}
              </span>
            </SelectItem>
          )}
        </ListBox>
      </Popover>
    </Select>
  );
}

function Field({
  label,
  children,
  error,
}: {
  label: string;
  children: React.ReactNode;
  error?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="font-medium text-sm">{label}</span>
      {children}
      <ErrorText>{error}</ErrorText>
    </div>
  );
}

export function CreatePoolSheet({
  isOpen,
  onOpenChange,
}: {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { schema: poolSchema } = useSchema("CoreNumberPool");
  const [kind, setKind] = React.useState<string | null>(null);
  const [attribute, setAttribute] = React.useState<string | null>(null);
  const [scope, setScope] = React.useState<string[]>([]);
  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [drafts, setDrafts] = React.useState<Draft[]>(() => [
    { key: newKey(), start: "", end: "", weight: "" },
  ]);
  const [submitted, setSubmitted] = React.useState(false);

  const schema = findKind(kind);
  const numberAttribute = schema?.numberAttributes.find((a) => a.name === attribute) ?? null;
  const rangeErrors = validate(drafts);
  const missing = {
    name: name.trim() === "" ? "Required" : undefined,
    allocates: !kind || !attribute ? "Select a node and one of its number attributes" : undefined,
  };
  const isValid = !missing.name && !missing.allocates && Object.keys(rangeErrors).length === 0;

  return (
    <Sheet
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      aria-label="Create number pool"
      className="flex flex-col p-0"
    >
      <div className="flex flex-1 flex-col gap-5 p-3">
        {poolSchema && (
          <SlideOverTitle
            schema={poolSchema}
            title="Create Number Pool"
            subtitle="Hands out numbers to an attribute, from one or more ranges."
          />
        )}

        <Field label="Name" error={submitted ? missing.name : undefined}>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={classNames(submitted && missing.name && inputErrorStyle)}
          />
        </Field>
        <Field label="Description">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full rounded-xl border border-input-border bg-input p-2 text-sm shadow-input focus-visible:border-ring focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring-halo"
          />
        </Field>

        <div className="flex flex-col gap-1.5">
          <span className="font-medium text-sm">What it allocates</span>
          <div className="grid grid-cols-[5rem_minmax(0,1fr)] items-center gap-2 rounded-xl border bg-card p-2.5 text-sm">
            <span className="text-foreground-muted">Node</span>
            <KindSelect
              kind={kind}
              onChange={(k) => {
                setKind(k);
                setAttribute(null);
                setScope([]);
              }}
            />
            <span className="text-foreground-muted">Attribute</span>
            <AttributeSelect schema={schema} attribute={attribute} onChange={setAttribute} />
            <span className="self-start pt-1.5 text-foreground-muted">Scoped by</span>
            <ScopeField schema={schema} scope={scope} setScope={setScope} />
          </div>
          <p className="text-foreground-muted text-xs">
            The scope is optional. Only required fields can be used, and every object needs a value
            for them.
          </p>
          {submitted && <ErrorText>{missing.allocates}</ErrorText>}
          {numberAttribute?.unique && scope.length > 0 && (
            <WarningNote>
              {attribute} must be unique across every {kind}, so the same number can't be used in
              two scopes. To reuse numbers per scope, make it unique together with the scope fields
              in the schema.
            </WarningNote>
          )}
        </div>

        <section className="flex flex-col gap-2">
          <RangesSectionHeader
            limits={
              numberAttribute
                ? {
                    attribute: numberAttribute.name,
                    min: numberAttribute.min,
                    max: numberAttribute.max,
                  }
                : undefined
            }
          />
          <RowsEditor
            drafts={drafts}
            setDrafts={setDrafts}
            errors={submitted ? rangeErrors : {}}
            limits={
              numberAttribute
                ? {
                    attribute: numberAttribute.name,
                    min: numberAttribute.min,
                    max: numberAttribute.max,
                  }
                : undefined
            }
          />
        </section>
      </div>

      <div className="sticky bottom-0 flex justify-end gap-2 border-t bg-secondary p-3">
        <Button variant="outline" onPress={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button
          variant="primary"
          onPress={() => {
            setSubmitted(true);
            if (!isValid) return;
            toast(
              <Alert
                type={ALERT_TYPES.SUCCESS}
                message="Number pool created (prototype, nothing saved)"
              />
            );
            onOpenChange(false);
          }}
        >
          Create pool
        </Button>
      </div>
    </Sheet>
  );
}
