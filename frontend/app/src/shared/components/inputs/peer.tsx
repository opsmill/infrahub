import { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import { AddRelationshipAction } from "@/entities/nodes/relationships/ui/add-relationship-action";
import { RelationshipComboboxList } from "@/entities/nodes/relationships/ui/relationship-combobox-list";
import { Combobox, ComboboxContent, ComboboxTrigger } from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { classNames } from "@/shared/utils/common";
import { PopoverTriggerProps } from "@radix-ui/react-popover";
import React from "react";
import { inputStyle } from "../ui/style";

export interface PeerInputProps extends Omit<PopoverTriggerProps, "value" | "onChange"> {
  className?: string;
  onChange: (value: Node | null) => void;
  peer: string;
  value: Node | null;
  options?: Array<Node>;
  parent?: { name?: string; value?: string };
}

export const PeerInput = React.forwardRef<React.ElementRef<typeof PopoverTrigger>, PeerInputProps>(
  ({ className, value, onChange, options, peer, parent, ...props }, ref) => {
    const [open, setOpen] = React.useState(false);

    return (
      <Combobox open={open} onOpenChange={setOpen}>
        <ComboboxTrigger
          ref={ref}
          {...props}
          className={classNames(
            inputStyle,
            "has-[>:last-child:focus-visible]:outline-hidden has-[>:last-child:focus-visible]:ring-2 has-[>:last-child:focus-visible]:ring-custom-blue-500 has-[>:last-child:focus-visible]:ring-offset-2",
            "cursor-pointer",
            className
          )}
        >
          {value?.display_label}
        </ComboboxTrigger>

        <ComboboxContent>
          <RelationshipComboboxList
            peer={peer}
            onSelect={(newValue) => {
              onChange(newValue);
              setOpen(false);
            }}
          />

          {!options && (
            <AddRelationshipAction
              peer={peer}
              onSuccess={(value) => {
                onChange(value);
                setOpen(false);
              }}
            />
          )}
        </ComboboxContent>
      </Combobox>
    );
  }
);
