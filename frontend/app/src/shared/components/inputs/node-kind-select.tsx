import type { PopoverTriggerProps } from "@radix-ui/react-popover";
import { useAtomValue } from "jotai";
import { useState } from "react";

import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

export interface NodeKindSelectProps extends Omit<PopoverTriggerProps, "value" | "onChange"> {
  className?: string;
  value: string | null;
  onChange: (kind: string | null) => void;
  placeholder?: string;
  filter?: (namespace: string) => boolean;
}

export const NodeKindSelect = ({
  className,
  value,
  onChange,
  placeholder = "Select a kind...",
  filter,
  ...props
}: NodeKindSelectProps) => {
  const [open, setOpen] = useState(false);
  const allNodes = useAtomValue(nodeSchemasAtom);
  const nodes = filter ? allNodes.filter((n) => filter(n.namespace as string)) : allNodes;
  const current = nodes.find((n) => n.kind === value);

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <ComboboxTrigger {...props} className={classNames(inputStyle, "cursor-pointer", className)}>
        {current ? (
          <div className="flex w-full justify-between">
            {current.label ?? current.kind} <Badge>{current.namespace}</Badge>
          </div>
        ) : (
          <span className="text-gray-400">{placeholder}</span>
        )}
      </ComboboxTrigger>

      <ComboboxContent>
        <ComboboxList>
          <ComboboxEmpty>No kinds found</ComboboxEmpty>
          {nodes.map((node) => (
            <ComboboxItem
              key={node.id}
              value={node.kind as string}
              keywords={[node.label as string]}
              selectedValue={value ?? undefined}
              onSelect={() => {
                const next = node.kind === value ? null : (node.kind as string);
                onChange(next);
                setOpen(false);
              }}
            >
              <div className="flex w-full justify-between">
                {node.label ?? node.kind} <Badge>{node.namespace}</Badge>
              </div>
            </ComboboxItem>
          ))}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
};
