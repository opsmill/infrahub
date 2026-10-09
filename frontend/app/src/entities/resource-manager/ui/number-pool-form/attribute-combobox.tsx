import { useState } from "react";

import {
  Combobox,
  ComboboxContent,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import { FormInput } from "@/shared/components/ui/form";

import { ATTRIBUTE_KIND } from "@/entities/schema/domain/model/attribute-kind";
import type { AttributeSchema } from "@/entities/schema/domain/model/schema";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function isAllocatableAttribute(attribute: AttributeSchema): boolean {
  return attribute.kind === ATTRIBUTE_KIND.NUMBER && !attribute.read_only;
}

interface AttributeComboboxProps {
  nodeKind?: string;
  value?: string;
  onSelect: (attributeName: string) => void;
}

export function AttributeCombobox({ nodeKind, value, onSelect }: AttributeComboboxProps) {
  const [open, setOpen] = useState(false);
  const { schema } = useSchema(nodeKind);
  const options = schema?.attributes?.filter(isAllocatableAttribute) ?? [];

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <FormInput>
        <ComboboxTrigger disabled={!schema}>
          {options.find((attribute) => attribute.name === value)?.label}
        </ComboboxTrigger>
      </FormInput>
      <ComboboxContent>
        <ComboboxList>
          {options.map((attribute) => (
            <ComboboxItem
              key={attribute.id ?? attribute.name}
              selectedValue={value}
              value={attribute.name}
              keywords={[attribute.label ?? attribute.name]}
              onSelect={() => {
                onSelect(attribute.name);
                setOpen(false);
              }}
            >
              {attribute.label}
            </ComboboxItem>
          ))}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
