import { ListBox, Popover, Select, SelectItem, SelectTrigger } from "@infrahub/ui";

import { Row } from "@/shared/components/container";

import { canNumberPoolAllocateTo } from "@/entities/resource-manager/domain/rules/can-number-pool-allocate-to";
import type { AttributeSchema, ModelSchema } from "@/entities/schema/domain/model/schema";

const numberFormat = new Intl.NumberFormat();

function formatLimits(attribute: AttributeSchema): string | null {
  const parameters = attribute.parameters;
  if (!parameters || !("min_value" in parameters || "max_value" in parameters)) return null;

  const min = "min_value" in parameters ? parameters.min_value : null;
  const max = "max_value" in parameters ? parameters.max_value : null;
  if (min == null && max == null) return null;

  return `${min == null ? "…" : numberFormat.format(min)} – ${max == null ? "…" : numberFormat.format(max)}`;
}

function getPlaceholder(schema: ModelSchema | null, attributeCount: number): string {
  if (!schema) return "Select a node first";
  if (attributeCount === 0) return "No editable Number attribute";
  return "Select an attribute";
}

export interface NumberPoolNodeAttributeSelectProps {
  schema: ModelSchema | null;
  value: string | null;
  onChange: (attributeName: string | null) => void;
  isInvalid?: boolean;
}

export function NumberPoolNodeAttributeSelect({
  schema,
  value,
  onChange,
  isInvalid,
}: NumberPoolNodeAttributeSelectProps) {
  const items = (schema?.attributes ?? []).filter(canNumberPoolAllocateTo).map((attribute) => ({
    id: attribute.name,
    label: attribute.label ?? attribute.name,
    limits: formatLimits(attribute),
    unique: attribute.unique,
  }));

  return (
    <Select
      aria-label="Attribute"
      placeholder={getPlaceholder(schema, items.length)}
      isDisabled={items.length === 0}
      value={value}
      onChange={(name) => onChange(name === null ? null : String(name))}
      isInvalid={isInvalid}
    >
      <SelectTrigger size="sm" />
      <Popover placement="bottom end" width="min-trigger">
        <ListBox selectionMode="single" items={items} className="max-h-72">
          {(item) => (
            <SelectItem textValue={item.label} className="items-baseline">
              <span className="min-w-0 truncate">{item.label}</span>
              <Row className="in-[button]:hidden text-subtle-muted text-xs tabular-nums">
                {item.limits && <span>{item.limits}</span>}
                {item.unique && <span>Unique</span>}
              </Row>
            </SelectItem>
          )}
        </ListBox>
      </Popover>
    </Select>
  );
}
