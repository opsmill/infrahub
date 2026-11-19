import { Button, Select, SelectItem, SelectList, SelectTrigger } from "@infrahub/ui";

import { Input } from "@/shared/components/ui/input";

import type { ValueSource, ValueSourceType } from "@/entities/rack-elevation/domain/model/mapping";
import type { AttributeValue, Schema } from "@/entities/rack-elevation/domain/model/schema";

const DISPLAY_LABEL_KEY = "__display_label__";

const MODES: { type: ValueSourceType; label: string }[] = [
  { type: "path", label: "Field" },
  { type: "template", label: "Template" },
  { type: "constant", label: "Fixed value" },
];

interface ValueSourceFieldProps {
  label: string;
  description: string;
  kind: string;
  schema: Schema;
  value: ValueSource;
  sample: AttributeValue | undefined;
  onChange: (value: ValueSource) => void;
}

function convert(value: ValueSource, type: ValueSourceType): ValueSource {
  if (type === "path") return { type, path: [] };
  if (type === "template") {
    return { type, template: value.type === "path" ? `{${value.path.join(".")}}` : "" };
  }
  return { type, value: "" };
}

export function ValueSourceField({
  label,
  description,
  kind,
  schema,
  value,
  sample,
  onChange,
}: ValueSourceFieldProps) {
  return (
    <div className="flex flex-col gap-2 border-b py-3 last:border-b-0 md:flex-row md:gap-4">
      <div className="md:w-40 md:shrink-0">
        <div className="font-medium text-sm">{label}</div>
        <div className="text-foreground-muted text-xs">{description}</div>
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex w-fit rounded-lg border bg-content-muted p-0.5">
          {MODES.map((mode) => (
            <Button
              key={mode.type}
              size="xxs"
              variant={value.type === mode.type ? "outline" : "ghost"}
              onPress={() => value.type !== mode.type && onChange(convert(value, mode.type))}
            >
              {mode.label}
            </Button>
          ))}
        </div>
        {value.type === "path" && (
          <PathPicker
            kind={kind}
            schema={schema}
            path={value.path}
            onChange={(path) => onChange({ type: "path", path })}
          />
        )}
        {value.type === "template" && (
          <Input
            aria-label={`${label} template`}
            value={value.template}
            placeholder="{name} · {serial_number}"
            onChange={(event) => onChange({ type: "template", template: event.target.value })}
          />
        )}
        {value.type === "constant" && (
          <Input
            aria-label={`${label} value`}
            value={value.value}
            onChange={(event) => onChange({ type: "constant", value: event.target.value })}
          />
        )}
        {sample !== undefined && (
          <div className="text-foreground-muted text-xs">
            Sample value:{" "}
            <span className="font-mono text-foreground">
              {sample === null || sample === "" ? "empty" : String(sample)}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

function PathPicker({
  kind,
  schema,
  path,
  onChange,
}: {
  kind: string;
  schema: Schema;
  path: string[];
  onChange: (path: string[]) => void;
}) {
  const levels: { kind: string; selected: string | null }[] = [];
  let currentKind: string | undefined = kind;
  for (let index = 0; currentKind; index++) {
    const schemaKind: Schema[string] | undefined = schema[currentKind];
    const segment = path[index];
    const relationship: Schema[string]["relationships"][number] | undefined =
      schemaKind?.relationships.find((candidate) => candidate.name === segment);
    const isAfterRelationship = index > 0;
    levels.push({
      kind: currentKind,
      selected: segment ?? (isAfterRelationship ? DISPLAY_LABEL_KEY : null),
    });
    currentKind = relationship?.peer;
  }

  return (
    <div className="flex flex-wrap items-center gap-1">
      {levels.map((level, index) => {
        const schemaKind = schema[level.kind];
        const options = [
          ...(index > 0 ? [{ id: DISPLAY_LABEL_KEY, label: "Display label" }] : []),
          ...(schemaKind?.attributes.map((attribute) => ({
            id: attribute.name,
            label: `${attribute.label} · ${attribute.kind}`,
          })) ?? []),
          ...(schemaKind?.relationships
            .filter((relationship) => relationship.cardinality === "one")
            .map((relationship) => ({
              id: relationship.name,
              label: `${relationship.label} →`,
            })) ?? []),
        ];
        return (
          <div key={`${level.kind}-${index}`} className="flex items-center gap-1">
            {index > 0 && <span className="text-foreground-muted text-xs">›</span>}
            <Select
              aria-label={`Field of ${schemaKind?.label ?? level.kind}`}
              className="w-44"
              placeholder={`Select from ${schemaKind?.label ?? level.kind}`}
              selectedKey={level.selected}
              onSelectionChange={(key) => {
                const head = path.slice(0, index);
                onChange(key === DISPLAY_LABEL_KEY ? head : [...head, String(key)]);
              }}
            >
              <SelectTrigger size="sm" />
              <SelectList items={options}>
                {(option) => <SelectItem id={option.id}>{option.label}</SelectItem>}
              </SelectList>
            </Select>
          </div>
        );
      })}
    </div>
  );
}
