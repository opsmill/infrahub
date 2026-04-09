import { Icon } from "@iconify-icon/react";

import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { RelationshipComboboxList } from "@/entities/nodes/relationships/ui/relationship-combobox-list";

interface RelationshipFilterComboboxProps {
  peer: string;
  value: RelationshipNode[] | undefined;
  onChange: (value: RelationshipNode[]) => void;
}

export function RelationshipFilterCombobox({
  peer,
  value,
  onChange,
}: RelationshipFilterComboboxProps) {
  return (
    <Combobox defaultOpen>
      <PopoverTrigger asChild>
        <div
          className={classNames(
            inputStyle,
            "has-[>:last-child:focus]:border-custom-blue-600 has-[>:last-child:focus]:outline-hidden has-[>:last-child:focus]:ring-2 has-[>:last-child:focus]:ring-custom-blue-600/25",
            "min-w-33 max-w-75 cursor-pointer"
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
                    onChange(value.filter((item) => item.id !== id));
                  }}
                  className="h-4 w-4 text-gray-500 hover:text-gray-800"
                  aria-label="Remove"
                  data-testid="remove-option"
                >
                  &times;
                </Button>
              </Badge>
            ))}
          </div>

          <button type="button" className="h-3.5 w-3.5 text-gray-600 outline-hidden">
            <Icon icon="mdi:unfold-more-horizontal" />
          </button>
        </div>
      </PopoverTrigger>

      <ComboboxContent fitTriggerWidth={false}>
        <RelationshipComboboxList
          peer={peer}
          onSelect={(relationship) => {
            onChange(value ? [...value, relationship] : [relationship]);
          }}
          filterItem={(node) => !value?.some((v) => v.id === node.id)}
        />
      </ComboboxContent>
    </Combobox>
  );
}
