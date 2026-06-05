import { Button, Spinner } from "@infrahub/ui";
import type { PopoverTriggerProps } from "@radix-ui/react-popover";
import React from "react";

import type { PoolValue } from "@/shared/components/form/pool-selector";
import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import type { PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import { useDebounce } from "@/shared/hooks/useDebounce";
import { classNames } from "@/shared/utils/common";

import type { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { AddRelationshipAction } from "@/entities/nodes/relationships/ui/add-relationship-action";
import { useRelationships } from "@/entities/nodes/relationships/ui/queries/get-relationships.query";

export interface RelationshipInputProps extends Omit<PopoverTriggerProps, "value" | "onChange"> {
  className?: string;
  onChange: (value: Node | PoolValue | null) => void;
  peer: string;
  value: Node | PoolValue | null;
  options?: Array<Node>;
  parent?: { name?: string; value?: string };
  ref?: React.Ref<React.ComponentRef<typeof PopoverTrigger>>;
}

export const RelationshipInput = ({
  className,
  value,
  onChange,
  options,
  peer,
  parent,
  ref,
  ...props
}: RelationshipInputProps) => {
  const [open, setOpen] = React.useState(false);
  const [search, setSearch] = React.useState("");
  const searchQuery = useDebounce(search, 500);

  const filterQuery =
    parent?.name && parent?.value ? { [`${parent.name}__ids`]: [parent.value] } : undefined;

  const {
    isFetching: isRelationshipListLoading,
    data,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useRelationships({ peer, search: searchQuery, filterQuery }, { enabled: open });

  const results = data?.pages.flat() ?? [];

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
            {"from_pool" in value ? "Allocated by pool" : getNodeLabel(value)}
          </span>
        )}

        {isRelationshipListLoading && <Spinner className="ml-auto" />}
      </ComboboxTrigger>

      <ComboboxContent>
        <ComboboxList
          shouldFilter={false}
          onValueChange={(newValue) => {
            setSearch(newValue);
          }}
        >
          {!isRelationshipListLoading && !error && <ComboboxEmpty>No results found</ComboboxEmpty>}

          {results.map((relationship) => {
            return (
              <ComboboxItem
                key={relationship.id}
                value={relationship.id}
                selectedValue={value?.id}
                onSelect={() => {
                  onChange(relationship.id === value?.id ? null : (relationship as Node));
                  setOpen(false);
                }}
              >
                <span className="truncate">{getNodeLabel(relationship)}</span>
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
                  <span className="grow truncate">{getNodeLabel(option)}</span>

                  {option.badge && <Badge className="mr-2">{option.badge}</Badge>}
                </ComboboxItem>
              );
            })}

          {isRelationshipListLoading && <Spinner className="m-2 flex justify-center" />}

          {hasNextPage && (
            <div className="pt-2">
              <Button
                variant={"ghost"}
                className="w-full border-custom-blue-500/10 font-normal text-custom-blue-700 not-data-disabled:data-hovered:bg-custom-blue-500/10"
                onPress={() => fetchNextPage()}
                isDisabled={isFetchingNextPage}
              >
                {isFetchingNextPage ? "Loading more..." : "Load more"}
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
};
