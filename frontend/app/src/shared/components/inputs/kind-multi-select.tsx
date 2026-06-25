import { Icon } from "@iconify-icon/react";
import { Button } from "@infrahub/ui";
import { useAtomValue } from "jotai";
import React from "react";

import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
} from "@/shared/components/ui/combobox";
import Label from "@/shared/components/ui/label";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

export interface KindMultiSelectProps {
  value: string[];
  onChange: (kinds: string[]) => void;
  label?: string;
  placeholder?: string;
  filter?: (namespace: string) => boolean;
  className?: string;
  id?: string;
}

export function KindMultiSelect({
  value,
  onChange,
  label,
  placeholder = "Select kinds...",
  filter,
  className,
  id: idProp,
}: KindMultiSelectProps) {
  const [open, setOpen] = React.useState(false);
  const generatedId = React.useId();
  const id = idProp ?? generatedId;
  const allNodes = useAtomValue(nodeSchemasAtom);
  const nodes = filter ? allNodes.filter((s) => filter(s.namespace as string)) : allNodes;

  function toggle(kind: string) {
    onChange(value.includes(kind) ? value.filter((k) => k !== kind) : [...value, kind]);
  }

  return (
    <div className="space-y-1">
      {label && (
        <Label htmlFor={id} className="inline-block w-fit">
          {label}
          {value.length > 0 && (
            <span className="ml-1 font-normal text-gray-400 text-xs">({value.length})</span>
          )}
        </Label>
      )}

      <Combobox open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <div
            className={classNames(
              inputStyle,
              "has-[>:last-child:focus]:border-custom-blue-600 has-[>:last-child:focus]:outline-hidden has-[>:last-child:focus]:ring-2 has-[>:last-child:focus]:ring-custom-blue-600/25",
              "cursor-pointer",
              className
            )}
          >
            <div className="flex grow flex-wrap gap-1">
              {value.length === 0 && <span className="text-gray-400 text-sm">{placeholder}</span>}
              {value.map((kind) => {
                const node = nodes.find((n) => n.kind === kind);
                return (
                  <Badge key={kind} className="flex items-center gap-1 pr-0.5">
                    {node?.label ?? kind}
                    <Button
                      size="xs"
                      shape="circle"
                      variant="ghost"
                      preventFocusOnPress
                      onPress={() => toggle(kind)}
                      className="size-4 text-gray-500 data-hovered:text-gray-800"
                      aria-label="Remove"
                      data-testid="remove-option"
                    >
                      &times;
                    </Button>
                  </Badge>
                );
              })}
            </div>

            <button
              id={id}
              type="button"
              className="h-3.5 w-3.5 text-gray-600 outline-hidden"
              onClick={() => setOpen(!open)}
            >
              <Icon icon="mdi:unfold-more-horizontal" />
            </button>
          </div>
        </PopoverTrigger>

        <ComboboxContent>
          <ComboboxList>
            <ComboboxEmpty>No kinds found</ComboboxEmpty>
            {nodes.map((s) => {
              const kind = s.kind as string;
              const checked = value.includes(kind);
              return (
                <ComboboxItem
                  key={kind}
                  value={kind}
                  selectedValue={checked ? kind : null}
                  keywords={[s.label as string, s.namespace as string]}
                  onSelect={() => toggle(kind)}
                >
                  <span className="truncate">{s.label ?? kind}</span>
                  <span className="ml-auto text-gray-400 text-xs">{s.namespace}</span>
                </ComboboxItem>
              );
            })}
          </ComboboxList>
        </ComboboxContent>
      </Combobox>
    </div>
  );
}
