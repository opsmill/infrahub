import { useState } from "react";

import { Row } from "@/shared/components/container";
import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import { inputErrorStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

export interface PoolKindOption {
  kind: string;
  label: string;
  namespace: string;
}

export interface PoolKindSelectProps {
  value: string | null | undefined;
  /** Kinds the allocation may target; the caller supplies them, this makes no lookup. */
  options: Array<PoolKindOption>;
  /** Pool's default target kind, shown as a hint of the kind allocated when left blank. */
  placeholder?: string;
  invalid?: boolean;
  /** Ties the caller's visible label to this control. */
  id?: string;
  disabled?: boolean;
  onChange: (kind: string | null) => void;
}

/**
 * Compact editor for a from-pool allocation's target-kind override. The pool field decides
 * when it is shown and which kinds are candidates; this just edits the choice.
 * Re-picking the selected kind emits `null` so react-hook-form writes the empty state,
 * which is what makes the pool's own default apply again.
 */
export function PoolKindSelect({
  value,
  options,
  placeholder,
  invalid,
  id,
  disabled,
  onChange,
}: PoolKindSelectProps) {
  const [open, setOpen] = useState(false);
  const selected = options.find((option) => option.kind === value);

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <ComboboxTrigger
        id={id}
        disabled={disabled}
        aria-label="Type to allocate"
        title="Type to allocate"
        data-testid="pool-kind-select"
        className={classNames("cursor-pointer", invalid && inputErrorStyle)}
      >
        {selected ? (
          <Row className="w-full justify-between">
            {selected.label} <Badge>{selected.namespace}</Badge>
          </Row>
        ) : (
          <span className="text-subtle-muted">{placeholder}</span>
        )}
      </ComboboxTrigger>

      <ComboboxContent>
        <ComboboxList>
          <ComboboxEmpty>No kinds found</ComboboxEmpty>
          {options.map((option) => (
            <ComboboxItem
              key={option.kind}
              value={option.kind}
              keywords={[option.label]}
              selectedValue={value ?? undefined}
              onSelect={() => {
                onChange(option.kind === value ? null : option.kind);
                setOpen(false);
              }}
            >
              <Row className="w-full justify-between">
                {option.label} <Badge>{option.namespace}</Badge>
              </Row>
            </ComboboxItem>
          ))}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
