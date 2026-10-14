import { Autocomplete, ListBox, Popover, Select, SelectItem, SelectTrigger } from "@infrahub/ui";
import { useAtomValue } from "jotai";
import { InfoIcon } from "lucide-react";

import { Row } from "@/shared/components/container";

import { canNumberPoolAllocateTo } from "@/entities/resource-manager/domain/rules/can-number-pool-allocate-to";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

export interface NumberPoolNodeSelectProps {
  value: string | null;
  onChange: (kind: string | null) => void;
  isInvalid?: boolean;
}

export function NumberPoolNodeSelect({ value, onChange, isInvalid }: NumberPoolNodeSelectProps) {
  const nodes = useAtomValue(nodeSchemasAtom);
  const generics = useAtomValue(genericSchemasAtom);
  const items = [...generics, ...nodes]
    .filter((schema) => schema.attributes?.some(canNumberPoolAllocateTo))
    .map((schema) => ({ id: schema.kind, kind: schema.kind, label: schema.label ?? schema.kind }));

  return (
    <Select
      aria-label="Node"
      placeholder="Select a node"
      value={value}
      onChange={(kind) => onChange(kind === null ? null : String(kind))}
      isInvalid={isInvalid}
    >
      <SelectTrigger size="sm" />
      <Popover placement="bottom end" width="min-trigger">
        <Autocomplete>
          <ListBox
            selectionMode="single"
            items={items}
            className="max-h-72"
            emptyMessage="No matching node"
          >
            {(item) => (
              <SelectItem textValue={`${item.label} ${item.kind}`} className="items-baseline">
                <span className="min-w-0 truncate">{item.label}</span>
                <span className="in-[button]:hidden min-w-0 truncate text-subtle-muted text-xs">
                  {item.kind}
                </span>
              </SelectItem>
            )}
          </ListBox>
        </Autocomplete>

        <Row className="border-border-strong border-t px-2 py-1.5 text-subtle-muted text-xs">
          <InfoIcon className="size-3" />
          <span>Only nodes with an editable Number attribute are listed.</span>
        </Row>
      </Popover>
    </Select>
  );
}
