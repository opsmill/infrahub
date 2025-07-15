import { NumberPool } from "@/entities/resource-manager/domain/get-number-pools";
import { Button } from "@/shared/components/buttons/button-primitive";
import { FormFieldValue } from "@/shared/components/form/type";
import { ComboboxContent, ComboboxItem, ComboboxList } from "@/shared/components/ui/combobox";
import { Popover, PopoverAnchor, PopoverTrigger } from "@/shared/components/ui/popover";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { Icon } from "@iconify-icon/react";
import { Slot } from "@radix-ui/react-slot";
import React, { forwardRef } from "react";

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
  pools: Array<NumberPool>;
  value: FormFieldValue;
};

export const PoolSelector = forwardRef<HTMLElement, PoolSelectorProps>(
  ({ children, onChange, value, pools }, ref) => {
    const [override, setOverride] = React.useState(false);

    const items = pools.map((pool) => ({
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
                className="flex gap-2 justify-start w-full border-gray-300 shadow-none h-10 px-2 font-normal"
              >
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
                data-testid="number-pool-button"
              >
                <Icon icon="mdi:view-grid-outline" className="text-gray-500" />
              </Button>
            </PopoverTrigger>
          </Tooltip>
        </div>

        <ComboboxContent portal={true}>
          <ComboboxList>
            {items.map((item) => (
              <ComboboxItem
                key={item.value.from_pool.id}
                value={item.value.from_pool.id}
                keywords={[item.label]}
                onSelect={() => onChange(item.value)}
                selectedValue={value?.source?.id}
              >
                {item.label}
              </ComboboxItem>
            ))}
          </ComboboxList>
        </ComboboxContent>
      </Popover>
    );
  }
);
