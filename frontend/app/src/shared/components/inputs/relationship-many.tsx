import { Icon } from "@iconify-icon/react";
import { Button } from "@infrahub/ui";
import type { PopoverTriggerProps } from "@radix-ui/react-popover";
import React from "react";

import { Badge } from "@/shared/components/ui/badge";
import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { AddRelationshipAction } from "@/entities/nodes/relationships/ui/add-relationship-action";
import { RelationshipComboboxList } from "@/entities/nodes/relationships/ui/relationship-combobox-list";
import type { NodeCore } from "@/entities/nodes/types";

export interface RelationshipManyInputProps
  extends Omit<PopoverTriggerProps, "value" | "onChange"> {
  className?: string;
  onChange: (value: Array<NodeCore>) => void;
  peer: string;
  value: Array<NodeCore> | null;
  filterQuery?: Record<string, string | number | boolean | string[]>;
  ref?: React.Ref<HTMLButtonElement>;
}

export function RelationshipManyInput({
  className,
  peer,
  value,
  onChange,
  filterQuery,
  ref,
  ...props
}: RelationshipManyInputProps) {
  const [open, setOpen] = React.useState(false);
  const handleSelect = (relationship: NodeCore) => {
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
            {value?.map((node) => (
              <Badge key={node.id} className="flex items-center gap-1 pr-0.5">
                {getNodeLabel(node)}

                <Button
                  size="xs"
                  shape="circle"
                  variant="ghost"
                  preventFocusOnPress
                  onPress={() => {
                    onChange(value.filter((item) => item.id !== node.id));
                  }}
                  className="size-4 text-gray-500 data-hovered:text-gray-800"
                  aria-label="Remove"
                  data-testid="remove-option"
                >
                  &times;
                </Button>
              </Badge>
            ))}
          </div>

          <button
            ref={ref}
            type="button"
            className="h-3.5 w-3.5 text-gray-600 outline-hidden"
            onClick={() => setOpen(!open)}
            {...props}
          >
            <Icon icon="mdi:unfold-more-horizontal" />
          </button>
        </div>
      </PopoverTrigger>

      <ComboboxContent>
        <RelationshipComboboxList
          peer={peer}
          onSelect={handleSelect}
          filterItem={(node) => !value?.some((v) => v.id === node.id)}
          filterQuery={filterQuery}
        />
        <AddRelationshipAction peer={peer} onSuccess={handleSelect} />
      </ComboboxContent>
    </Combobox>
  );
}
