import { RelationshipComboboxList } from "@/entities/nodes/relationships/ui/relationship-combobox-list";
import { Button } from "@/shared/components/buttons/button-primitive";
import { PoolValue } from "@/shared/components/form/pool-selector";
import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { Icon } from "@iconify-icon/react";
import React from "react";

export interface PoolSelectProps {
  poolKind: string;
  selectedPoolId: string | null;
  onChange: (value: PoolValue | null) => void;
}

export function PoolSelect({ poolKind, onChange, selectedPoolId }: PoolSelectProps) {
  const [isOpen, setIsOpen] = React.useState(false);

  return (
    <Combobox open={isOpen} onOpenChange={setIsOpen}>
      <Tooltip content="select a pool" enabled>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            className="h-10 w-10 border-gray-300"
            data-testid="select-open-pool-option-button"
          >
            <Icon icon="mdi:view-grid-outline" className="text-gray-500" />
          </Button>
        </PopoverTrigger>
      </Tooltip>

      <ComboboxContent align="end" fitTriggerWidth={false}>
        <RelationshipComboboxList
          onSelect={(pool) => {
            if (selectedPoolId === pool.id) {
              onChange(null);
            } else {
              onChange({
                from_pool: {
                  id: pool.id,
                  name: pool.display_label,
                  kind: pool.__typename,
                },
              });
            }
            setIsOpen(false);
          }}
          peer={poolKind}
        />
      </ComboboxContent>
    </Combobox>
  );
}
