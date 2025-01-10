import { POOLS_DICTIONNARY, POOLS_PEER } from "@/entities/ipam/constants";
import { getDropdownOptions } from "@/entities/nodes/api/dropdownOptions";
import { generateRelationshipListQuery } from "@/entities/nodes/api/generateRelationshipListQuery";
import { Node, RelationshipManyType } from "@/entities/nodes/getObjectItemDisplayValue";
import { AddRelationshipAction } from "@/entities/nodes/relationships/ui/add-relationship-action";
import { useSchema } from "@/entities/schema/useSchema";
import { useLazyQuery } from "@/shared/api/graphql/useQuery";
import { Button } from "@/shared/components/buttons/button-primitive";
import { PoolValue } from "@/shared/components/form/pool-selector";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { Spinner } from "@/shared/components/ui/spinner";
import { useDebounce } from "@/shared/hooks/useDebounce";
import { classNames } from "@/shared/utils/common";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { PopoverTriggerProps } from "@radix-ui/react-popover";
import React, { useEffect, useState } from "react";
import { Badge } from "../ui/badge";
import { inputStyle } from "../ui/style";
import { Tooltip } from "../ui/tooltip";

export interface RelationshipInputProps extends Omit<PopoverTriggerProps, "value" | "onChange"> {
  className?: string;
  onChange: (value: Node | PoolValue | null) => void;
  peer: string;
  value: Node | PoolValue | null;
  options?: Array<Node>;
  parent?: { name?: string; value?: string };
}

const PAGINATION = 20;

export const RelationshipInput = React.forwardRef<
  React.ElementRef<typeof PopoverTrigger>,
  RelationshipInputProps
>(({ className, value, onChange, options, peer, parent, ...props }, ref) => {
  const { schema, isNode } = useSchema(peer);
  const [open, setOpen] = React.useState(false);
  const [count, setCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [results, setResults] = useState([]);
  const [search, setSearch] = useState("");
  const [shouldAggregate, setShouldAggregate] = useState(true);
  const searchQuery = useDebounce(search, 500);
  const [isPoolOpen, setIsPoolOpen] = React.useState(false);

  // Check if any kind from inheritance is one of the available for pools
  const canRequestPools =
    isNode &&
    !!schema?.inherit_from?.map((from) => POOLS_PEER.includes(from))?.filter(Boolean)?.length;
  const poolPeer = canRequestPools && POOLS_DICTIONNARY[peer];
  const poolsQueryString = poolPeer ? getDropdownOptions({ kind: poolPeer }) : "query { ok }";
  const poolsQuery = gql`
    ${poolsQueryString}
  `;

  const [loadRelationshipList, { loading: isRelationshipListLoading, data: RelationshipListData }] =
    useLazyQuery(
      gql(
        generateRelationshipListQuery({
          peer,
          parent,
          limit: PAGINATION,
          offset,
          search: searchQuery,
        })
      )
    );

  const [loadPoolList, { loading: isPoolListLoading, data: poolsData }] = useLazyQuery(poolsQuery);

  const loading = isRelationshipListLoading || isPoolListLoading;

  useEffect(() => {
    const newResults =
      RelationshipListData &&
      (RelationshipListData[peer] as RelationshipManyType).edges.map((edge) => edge.node);

    const dataCount =
      RelationshipListData && (RelationshipListData[peer] as RelationshipManyType).count;

    setCount(dataCount);

    if (!shouldAggregate) {
      setResults(newResults);
      return;
    }

    if (!newResults) {
      return;
    }

    setResults([...results, ...newResults]);
  }, [RelationshipListData]);

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <div className={classNames("flex gap-2")}>
        <ComboboxTrigger
          ref={ref}
          {...props}
          className={classNames(
            inputStyle,
            "has-[>:last-child:focus-visible]:outline-none has-[>:last-child:focus-visible]:ring-2 has-[>:last-child:focus-visible]:ring-custom-blue-500 has-[>:last-child:focus-visible]:ring-offset-2",
            "cursor-pointer",
            className
          )}
        >
          {value && (
            <span data-testid="select-value">
              {"from_pool" in value ? "Allocated by pool" : value.display_label}
            </span>
          )}

          {loading && <Spinner className="ml-auto" />}
        </ComboboxTrigger>

        {canRequestPools && (
          <Combobox open={isPoolOpen} onOpenChange={setIsPoolOpen}>
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

            <ComboboxContent align="end" onOpenAutoFocus={() => loadPoolList()}>
              <ComboboxList style={{ width: "auto" }}>
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
                          selectedValue={
                            value && "from_pool" in value ? value.from_pool.id : value?.id
                          }
                          onSelect={() => {
                            onChange(
                              value && "from_pool" in value && value.from_pool.id === pool.id
                                ? null
                                : {
                                    from_pool: {
                                      id: pool.id,
                                      name: pool.display_label,
                                      kind: pool.__typename,
                                    },
                                  }
                            );
                            setIsPoolOpen(false);
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
        )}
      </div>

      <ComboboxContent
        onOpenAutoFocus={() => {
          setOffset(0);
          setShouldAggregate(false);
          loadRelationshipList();
        }}
      >
        <ComboboxList
          shouldFilter={false}
          onValueChange={(newValue) => {
            setOffset(0);
            setShouldAggregate(false);
            setSearch(newValue);
          }}
        >
          {!isRelationshipListLoading && <ComboboxEmpty>No results found</ComboboxEmpty>}

          {results?.map((relationship) => {
            return (
              <ComboboxItem
                key={relationship.id}
                value={relationship.id}
                selectedValue={value?.id}
                onSelect={() => {
                  onChange(relationship.id === value?.id ? null : relationship);
                  setOpen(false);
                }}
              >
                <span className="truncate">{relationship.display_label}</span>
              </ComboboxItem>
            );
          })}

          {options &&
            options.map((option) => {
              return (
                <ComboboxItem
                  key={option.id}
                  value={option.display_label}
                  onSelect={() => {
                    onChange(option);
                    setOpen(false);
                  }}
                >
                  <span className="truncate flex-grow">{option.display_label}</span>

                  {option.badge && <Badge className="mr-2">{option.badge}</Badge>}
                </ComboboxItem>
              );
            })}

          {loading && <Spinner className="flex justify-center m-2" />}

          {results?.length < count && (
            <div className="pt-2">
              <Button
                variant={"ghost"}
                className="w-full border-custom-blue-500/10 text-custom-blue-700 enabled:hover:bg-custom-blue-500/10 font-normal"
                onClick={() => {
                  setOffset(offset + PAGINATION);
                  setShouldAggregate(true);
                }}
              >
                Load more
              </Button>
            </div>
          )}
        </ComboboxList>

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
});
