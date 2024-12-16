import { Combobox, ComboboxContent, ComboboxTrigger } from "@/components/ui/combobox";
import {
  PopoverTabs,
  PopoverTabsContent,
  PopoverTabsList,
  PopoverTabsTrigger,
} from "@/components/ui/popover";
import { RelationshipComboboxList } from "@/screens/objects/relationships/components/relationship-combobox-list";
import { RelationshipHierarchicalComboboxList } from "@/screens/objects/relationships/components/relationship-hierarchical-combobox-list";
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
        <PopoverTabs defaultValue="list">
          <PopoverTabsList className="mt-1">
            <PopoverTabsTrigger value="list">All</PopoverTabsTrigger>
            <PopoverTabsTrigger value="tree">Explore</PopoverTabsTrigger>
          </PopoverTabsList>

          <PopoverTabsContent value="list">
            <RelationshipComboboxList
              peer={peer}
              value={value}
              onSelect={(relationshipNode) => {
                onChange(relationshipNode);
                setOpen(false);
              }}
            />
          </PopoverTabsContent>

          <PopoverTabsContent
            value="tree"
            style={{
              maxHeight: "min(var(--radix-popover-content-available-height), 300px)",
              width: "var(--radix-popover-trigger-width)",
            }}
          >
            <RelationshipHierarchicalComboboxList
              peer={peer}
              value={value}
              onSelect={(relationshipNode) => {
                onChange(relationshipNode);
                setOpen(false);
              }}
            />
          </PopoverTabsContent>
        </PopoverTabs>
      </ComboboxContent>
    </Combobox>
  );
};
