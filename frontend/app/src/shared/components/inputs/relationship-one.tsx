import { gql } from "@apollo/client";
import type { PopoverTriggerProps } from "@radix-ui/react-popover";
import React, { useEffect, useState } from "react";

import { useLazyQuery } from "@/shared/api/graphql/useQuery";
import { Button } from "@/shared/components/buttons/button-primitive";
import type { PoolValue } from "@/shared/components/form/pool-selector";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import type { PopoverTrigger } from "@/shared/components/ui/popover";
import { Spinner } from "@/shared/components/ui/spinner";
import { useDebounce } from "@/shared/hooks/useDebounce";
import { classNames } from "@/shared/utils/common";

import { generateRelationshipListQuery } from "@/entities/nodes/api/generateRelationshipListQuery";
import type { Node, RelationshipManyType } from "@/entities/nodes/getObjectItemDisplayValue";
import { AddRelationshipAction } from "@/entities/nodes/relationships/ui/add-relationship-action";

import { Badge } from "../ui/badge";
import { inputStyle } from "../ui/style";

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
  const [open, setOpen] = React.useState(false);
  const [count, setCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [results, setResults] = useState([]);
  const [search, setSearch] = useState("");
  const [shouldAggregate, setShouldAggregate] = useState(true);
  const searchQuery = useDebounce(search, 500);

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
      <ComboboxTrigger
        ref={ref}
        {...props}
        className={classNames(
          inputStyle,
          "has-[>:last-child:focus-visible]:outline-hidden has-[>:last-child:focus-visible]:ring-2 has-[>:last-child:focus-visible]:ring-custom-blue-500 has-[>:last-child:focus-visible]:ring-offset-2",
          "cursor-pointer",
          className
        )}
      >
        {value && (
          <span data-testid="select-value">
            {"from_pool" in value ? "Allocated by pool" : value.display_label}
          </span>
        )}

        {isRelationshipListLoading && <Spinner className="ml-auto" />}
      </ComboboxTrigger>

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
                  <span className="grow truncate">{option.display_label}</span>

                  {option.badge && <Badge className="mr-2">{option.badge}</Badge>}
                </ComboboxItem>
              );
            })}

          {isRelationshipListLoading && <Spinner className="m-2 flex justify-center" />}

          {results?.length < count && (
            <div className="pt-2">
              <Button
                variant={"ghost"}
                className="w-full border-custom-blue-500/10 font-normal text-custom-blue-700 enabled:hover:bg-custom-blue-500/10"
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
