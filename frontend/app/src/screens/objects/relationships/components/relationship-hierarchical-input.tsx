import { Combobox, ComboboxContent, ComboboxTrigger } from "@/components/ui/combobox";
import { RelationshipComboboxList } from "@/screens/objects/relationships/components/relationship-combobox-list";
import { RelationshipNode } from "@/screens/objects/relationships/domain/types";
import { useState } from "react";

export interface IHierarchicalRelationshipInputProps {
  onChange: (value: RelationshipNode) => void;
  value?: RelationshipNode | null;
  peer: string;
}

export const RelationshipHierarchicalInput = ({
  value,
  onChange,
  peer,
}: IHierarchicalRelationshipInputProps) => {
  const [open, setOpen] = useState(false);

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <ComboboxTrigger>{value?.display_label}</ComboboxTrigger>

      <ComboboxContent>
        <RelationshipComboboxList
          peer={peer}
          onSelect={(relationshipNode) => {
            onChange(relationshipNode);
            setOpen(false);
          }}
        />
      </ComboboxContent>
    </Combobox>
  );
};
