import React, { forwardRef } from "react";
import { FormFieldValue, NumberPoolData } from "@/components/form/type";
import { ComboboxList, tComboboxItem } from "@/components/ui/combobox-legacy";
import { Popover, PopoverAnchor, PopoverTrigger } from "@/components/ui/popover";
import { Slot } from "@radix-ui/react-slot";
import { Button } from "@/components/buttons/button-primitive";
import { Icon } from "@iconify-icon/react";
import { Tooltip } from "@/components/ui/tooltip";
import { Combobox as ComboboxPrimitive } from "@headlessui/react";

export type PoolValue = {
  from_pool: {
    id: string;
    name: string;
    kind: string;
  };
};

type PoolSelectorProps = {
  children: React.ReactNode;
  onChange: (value: PoolValue) => void;
  onReset: () => void;
  pools: Array<NumberPoolData>;
  value: FormFieldValue;
};

export const PoolSelector = forwardRef<HTMLElement, PoolSelectorProps>(
  ({ children, onChange, onReset, value, pools }, ref) => {
    const [override, setOverride] = React.useState(false);

    const items: Array<tComboboxItem> = pools.map((pool) => ({
      label: pool.label,
      value: {
        from_pool: {
          id: pool.id,
          name: pool.label,
          kind: pool.kind,
        },
      },
    }));

    const displayFromPool =
      typeof value.value === "object" && value.value && "from_pool" in value.value;

    return (
      <Popover>
        <div className="flex gap-1 w-full">
          <PopoverAnchor asChild>
            {value.source?.type !== "pool" || override || !displayFromPool ? (
              <Slot autoFocus={override} onBlur={() => setOverride(false)} ref={ref}>
                {children}
              </Slot>
            ) : (
              <Button
                variant="outline"
                onClick={() => setOverride(true)}
                className="flex gap-2 justify-start w-full border-gray-300 shadow-none h-10 px-2 font-normal">
                <Icon icon="mdi:view-grid-outline" />
                <span>{value.source.label}</span>
              </Button>
            )}
          </PopoverAnchor>

          <Tooltip content="select a pool" enabled>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                className="h-10 w-10 border-gray-300"
                data-testid="number-pool-button">
                <Icon icon="mdi:view-grid-outline" className="text-gray-500" />
              </Button>
            </PopoverTrigger>
          </Tooltip>
        </div>

        <ComboboxPrimitive onChange={onChange}>
          <ComboboxList items={items} onReset={onReset} />
        </ComboboxPrimitive>
      </Popover>
    );
  }
);
