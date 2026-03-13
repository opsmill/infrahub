import type { PopoverTriggerProps } from "@radix-ui/react-popover";
import React from "react";

import { Combobox, ComboboxContent, ComboboxTrigger } from "@/shared/components/ui/combobox";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import type { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { AddRelationshipAction } from "@/entities/nodes/relationships/ui/add-relationship-action";
import { RelationshipComboboxList } from "@/entities/nodes/relationships/ui/relationship-combobox-list";

export interface PeerInputProps extends Omit<PopoverTriggerProps, "value" | "onChange"> {
  className?: string;
  onChange: (value: Node | null) => void;
  peer: string;
  value: Node | null;
  options?: Array<Node>;
  parent?: { name?: string; value?: string };
}

export const PeerInput = ({
  className,
  value,
  onChange,
  options,
  peer,
  parent,
  ...props
}: PeerInputProps) => {
  const [open, setOpen] = React.useState(false);

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <ComboboxTrigger
        {...props}
        className={classNames(
          inputStyle,
          "has-[>:last-child:focus-visible]:outline-hidden has-[>:last-child:focus-visible]:ring-2 has-[>:last-child:focus-visible]:ring-custom-blue-500 has-[>:last-child:focus-visible]:ring-offset-2",
          "cursor-pointer",
          className
        )}
      >
        {value ? getNodeLabel(value) : ""}
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
};
