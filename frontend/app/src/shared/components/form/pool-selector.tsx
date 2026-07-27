import { Icon } from "@iconify-icon/react";
import { Button, Tooltip } from "@infrahub/ui";
import type { PopoverTriggerProps } from "@radix-ui/react-popover";
import { Slot } from "@radix-ui/react-slot";
import React from "react";

import { Row } from "@/shared/components/container";
import type { FormFieldValue } from "@/shared/components/form/type";
import { ComboboxContent, ComboboxItem, ComboboxList } from "@/shared/components/ui/combobox";
import { Popover, PopoverTrigger } from "@/shared/components/ui/popover";
import { classNames } from "@/shared/utils/common";

import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import type { NumberPool } from "@/entities/resource-manager/domain/model/number-pool";

export type PoolValue = {
  from_pool: {
    id: string;
    name: string;
    kind: string;
  };
};

type PoolSelectorProps = {
  children: React.ReactNode;
  onChange: (value: PoolValue | null) => void;
  pools: Array<NumberPool>;
  value: FormFieldValue;
  className?: string;
};

export function PoolSelector({
  children,
  className,
  onChange,
  value,
  pools,
  ...props
}: PoolSelectorProps) {
  const [override, setOverride] = React.useState(false);

  const displayFromPool =
    typeof value.value === "object" && value.value && "from_pool" in value.value;

  return (
    <Popover>
      <Row className="gap-1">
        {value.source?.type !== "pool" || override || !displayFromPool ? (
          <Slot
            autoFocus={override}
            onBlur={() => setOverride(false)}
            className={className}
            {...props}
          >
            {children}
          </Slot>
        ) : (
          <Button
            variant="input"
            onPress={() => setOverride(true)}
            className={classNames("min-h-10 w-full p-2", className)}
            {...props}
          >
            Allocated by pool
          </Button>
        )}

        <PoolPopoverTrigger data-testid="number-pool-button" />
      </Row>

      <ComboboxContent align="end" fitTriggerWidth={false}>
        <ComboboxList>
          {pools.map((pool) => {
            const poolLabel = getNodeLabel(pool);
            return (
              <ComboboxItem
                key={pool.id}
                value={pool.id}
                keywords={[poolLabel, pool.id]}
                onSelect={() => {
                  if (value.source?.type !== "pool") {
                    onChange({
                      from_pool: {
                        id: pool.id,
                        name: poolLabel,
                        kind: pool.__typename,
                      },
                    });
                    return;
                  }
                  onChange(
                    value.source.id === pool.id
                      ? null
                      : {
                          from_pool: {
                            id: pool.id,
                            name: poolLabel,
                            kind: pool.__typename,
                          },
                        }
                  );
                }}
                selectedValue={value.source?.type === "pool" ? value.source.id : null}
              >
                {poolLabel}
              </ComboboxItem>
            );
          })}
        </ComboboxList>
      </ComboboxContent>
    </Popover>
  );
}

export function PoolPopoverTrigger({ className, ...props }: PopoverTriggerProps) {
  return (
    <Tooltip message="select a pool">
      <PopoverTrigger asChild {...props}>
        <Button variant="input" shape="square" className="size-10 justify-center">
          <Icon icon="mdi:view-grid-outline" className="text-neutral-500" />
        </Button>
      </PopoverTrigger>
    </Tooltip>
  );
}
