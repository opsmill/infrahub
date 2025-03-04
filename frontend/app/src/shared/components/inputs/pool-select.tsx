import { POOLS_DICTIONNARY } from "@/entities/ipam/constants";
import { getDropdownOptions } from "@/entities/nodes/api/dropdownOptions";
import { Node, RelationshipManyType } from "@/entities/nodes/getObjectItemDisplayValue";
import { useLazyQuery } from "@/shared/api/graphql/useQuery";
import { Button } from "@/shared/components/buttons/button-primitive";
import { PoolValue } from "@/shared/components/form/pool-selector";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
} from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { Spinner } from "@/shared/components/ui/spinner";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import React from "react";

export interface PoolSelectProps {
  peer: string;
  selectedPoolId: string | null;
  onChange: (value: PoolValue | null) => void;
}

export function PoolSelect({ peer, onChange, selectedPoolId }: PoolSelectProps) {
  const [isOpen, setIsOpen] = React.useState(false);

  const poolPeer = POOLS_DICTIONNARY[peer];
  const poolsQueryString = poolPeer ? getDropdownOptions({ kind: poolPeer }) : "query { ok }";
  const poolsQuery = gql`
    ${poolsQueryString}
  `;
  const [loadPoolList, { loading: isPoolListLoading, data: poolsData }] = useLazyQuery(poolsQuery);

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

      <ComboboxContent align="end" fitTriggerWidth={false} onOpenAutoFocus={() => loadPoolList()}>
        <ComboboxList>
          {!isPoolListLoading && <ComboboxEmpty>No pools found</ComboboxEmpty>}

          {!isPoolListLoading &&
            poolsData &&
            (poolsData[poolPeer] as RelationshipManyType).edges
              .map((edge) => edge.node)
              .filter((node): node is Node => !!node)
              .map((pool) => {
                return (
                  <ComboboxItem
                    key={pool.id}
                    value={pool.id}
                    keywords={[pool.display_label]}
                    selectedValue={selectedPoolId}
                    onSelect={() => {
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
                  >
                    <span className="truncate">{pool.display_label}</span>
                  </ComboboxItem>
                );
              })}

          {isPoolListLoading && <Spinner className="flex justify-center m-2" />}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
