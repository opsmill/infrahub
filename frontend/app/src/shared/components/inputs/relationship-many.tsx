import { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import { AddRelationshipAction } from "@/entities/nodes/relationships/ui/add-relationship-action";
import { RelationshipComboboxList } from "@/entities/nodes/relationships/ui/relationship-combobox-list";
import { Button } from "@/shared/components/buttons/button-primitive";
import { Badge } from "@/shared/components/ui/badge";
import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { PopoverTriggerProps } from "@radix-ui/react-popover";
import React from "react";

export interface RelationshipManyInputProps
  extends Omit<PopoverTriggerProps, "value" | "onChange"> {
  className?: string;
  onChange: (value: Array<Node>) => void;
  peer: string;
  value: Array<Node> | null;
  peerField?: string;
  ref?: React.Ref<HTMLButtonElement>;
}

export const RelationshipManyInput = ({
  id,
  className,
  peer,
  peerField,
  value,
  onChange,
  ref,
  ...props
}: RelationshipManyInputProps) => {
  const handleSelect = (relationship: Node) => {
    onChange(value ? [...value, relationship] : [relationship]);
  };

  return (
    <Combobox>
      <PopoverTrigger asChild>
        <div
          className={classNames(
            inputStyle,
            "has-[>:last-child:focus]:outline-none has-[>:last-child:focus]:ring-2 has-[>:last-child:focus]:ring-custom-blue-600/25  has-[>:last-child:focus]:border-custom-blue-600",
            "cursor-pointer",
            className
          )}
        >
          <div className="flex-grow flex flex-wrap gap-2">
            {value?.map(({ id, display_label, ...data }) => (
              <Badge key={id} className="flex items-center gap-1 pr-0.5">
                {peerField ? (data[peerField]?.value ?? display_label) : display_label}

                <Button
                  size="icon"
                  variant="ghost"
                  onClick={(e) => {
                    e.stopPropagation();
                    onChange(value.filter((item) => item.id !== id));
                  }}
                  className="text-gray-500 hover:text-gray-800 h-4 w-4"
                  aria-label="Remove"
                  data-testid="remove-option"
                >
                  &times;
                </Button>
              </Badge>
            ))}
          </div>

          <PopoverTrigger ref={ref} asChild {...props}>
            <button id={id} type="button" className="text-gray-600 outline-none w-3.5 h-3.5">
              <Icon icon="mdi:unfold-more-horizontal" />
            </button>
          </PopoverTrigger>
        </div>
      </PopoverTrigger>

      <ComboboxContent>
        <RelationshipComboboxList
          peer={peer}
          onSelect={handleSelect}
          filterItem={(node) => !value?.some((v) => v.id === node.id)}
        />
        <AddRelationshipAction peer={peer} onSuccess={handleSelect} />
      </ComboboxContent>
    </Combobox>
  );
};
