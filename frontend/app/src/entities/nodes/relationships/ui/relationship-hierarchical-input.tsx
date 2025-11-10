import { Icon } from "@iconify-icon/react";
import { forwardRef, useState } from "react";

import { Button } from "@/shared/components/buttons/button-primitive";
import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxTrigger,
  type ComboboxTriggerProps,
} from "@/shared/components/ui/combobox";
import {
  PopoverTabs,
  PopoverTabsContent,
  PopoverTabsList,
  PopoverTabsTrigger,
  PopoverTrigger,
} from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import type { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { AddRelationshipAction } from "@/entities/nodes/relationships/ui/add-relationship-action";
import {
  RelationshipComboboxList,
  type RelationshipComboboxListProps,
} from "@/entities/nodes/relationships/ui/relationship-combobox-list";
import { RelationshipHierarchicalComboboxList } from "@/entities/nodes/relationships/ui/relationship-hierarchical-combobox-list";

export interface RelationshipHierarchicalContentProps extends RelationshipComboboxListProps {}

export const RelationshipHierarchicalContent = ({
  ...props
}: RelationshipHierarchicalContentProps) => {
  return (
    <ComboboxContent>
      <PopoverTabs defaultValue="list">
        <PopoverTabsList className="mt-1">
          <PopoverTabsTrigger value="list">All</PopoverTabsTrigger>
          <PopoverTabsTrigger value="tree">Explore</PopoverTabsTrigger>
        </PopoverTabsList>

        <PopoverTabsContent value="list">
          <RelationshipComboboxList {...props} />
          <AddRelationshipAction {...props} />
        </PopoverTabsContent>

        <PopoverTabsContent value="tree">
          <RelationshipHierarchicalComboboxList {...props} />
        </PopoverTabsContent>
      </PopoverTabs>
    </ComboboxContent>
  );
};

export interface RelationshipHierarchicalInputProps
  extends Omit<ComboboxTriggerProps, "value" | "onChange"> {
  onChange?: (value: RelationshipNode | null) => void;
  value?: RelationshipNode | null;
  peer: string;
}

export const RelationshipHierarchicalInput = forwardRef<
  HTMLButtonElement,
  RelationshipHierarchicalInputProps
>(({ value, onChange, peer, ...props }, ref) => {
  const [open, setOpen] = useState(false);

  const handleSelect = (relationship: RelationshipNode) => {
    onChange?.(relationship.id === value?.id ? null : relationship);
    setOpen(false);
  };

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <ComboboxTrigger ref={ref} {...props}>
        {value?.display_label}
      </ComboboxTrigger>

      <RelationshipHierarchicalContent peer={peer} onSelect={handleSelect} value={value} />
    </Combobox>
  );
});

export interface RelationshipHierarchicalManyInputProps
  extends Omit<ComboboxTriggerProps, "value" | "onChange"> {
  onChange: (value: RelationshipNode[]) => void;
  value?: RelationshipNode[] | null;
  peer: string;
}

export const RelationshipHierarchicalManyInput = forwardRef<
  HTMLButtonElement,
  RelationshipHierarchicalManyInputProps
>(({ value, onChange, peer, className, ...props }, ref) => {
  const [open, setOpen] = useState(false);

  const handleSelect = (relationship: Node) => {
    onChange(value ? [...value, relationship] : [relationship]);
  };

  return (
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
          <div className="flex grow flex-wrap gap-2">
            {value?.map(({ id, display_label }) => (
              <Badge key={id} className="flex items-center gap-1 pr-0.5">
                {display_label}

                <Button
                  size="icon"
                  variant="ghost"
                  onClick={(e) => {
                    e.stopPropagation();
                    onChange(value?.filter((item) => item.id !== id));
                  }}
                  className="h-4 w-4 text-gray-500 hover:text-gray-800"
                  aria-label={`Remove ${display_label}`}
                  data-testid="remove-option"
                >
                  &times;
                </Button>
              </Badge>
            ))}
          </div>

          <PopoverTrigger ref={ref} asChild {...props}>
            <button
              type="button"
              className="h-3.5 w-3.5 text-gray-600 outline-hidden"
              aria-label={`Open ${peer}`}
            >
              <Icon icon="mdi:unfold-more-horizontal" />
            </button>
          </PopoverTrigger>
        </div>
      </PopoverTrigger>

      <RelationshipHierarchicalContent
        peer={peer}
        onSelect={handleSelect}
        filterItem={(node) => !value?.some((v) => v.id === node.id)}
      />
    </Combobox>
  );
});
