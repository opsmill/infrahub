import { Button } from "@/components/buttons/button-primitive";
import { Badge } from "@/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
} from "@/components/ui/combobox";
import { PopoverTrigger } from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";
import { inputStyle } from "@/components/ui/style";
import { generateRelationshipListQuery } from "@/shared/api/graphql/queries/objects/generateRelationshipListQuery";
import { useDebounce } from "@/hooks/useDebounce";
import { useLazyQuery } from "@/hooks/useQuery";
import { AddRelationshipAction } from "@/screens/objects/relationships/ui/add-relationship-action";
import { classNames } from "@/utils/common";
import { Node, RelationshipManyType } from "@/utils/getObjectItemDisplayValue";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { PopoverTriggerProps } from "@radix-ui/react-popover";
import React, { useEffect, useState } from "react";

export interface RelationshipManyInputProps
  extends Omit<PopoverTriggerProps, "value" | "onChange"> {
  className?: string;
  onChange: (value: Array<Node>) => void;
  peer: string;
  value: Array<Node> | null;
  peerField?: string;
}

const PAGINATION = 20;

export const RelationshipManyInput = React.forwardRef<
  React.ElementRef<typeof PopoverTrigger>,
  RelationshipManyInputProps
>(({ id, className, peer, peerField, value, onChange, ...props }, ref) => {
  const [open, setOpen] = React.useState(false);
  const [count, setCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [results, setResults] = useState([]);
  const [search, setSearch] = useState("");
  const [shouldAggregate, setShouldAggregate] = useState(true);
  const searchQuery = useDebounce(search, 500);

  const [loadComboboxList, { loading, data }] = useLazyQuery(
    gql(
      generateRelationshipListQuery({
        peer,
        peerField,
        limit: PAGINATION,
        offset,
        search: searchQuery,
      })
    )
  );

  const handleSelect = (relationship: Node) => {
    onChange(value ? [...value, relationship] : [relationship]);
  };

  useEffect(() => {
    const newResults =
      data &&
      (data[peer] as RelationshipManyType).edges
        .map((edge) => edge.node)
        .filter((node): node is Node => !!node);

    const dataCount = data && (data[peer] as RelationshipManyType).count;

    setCount(dataCount);

    if (!shouldAggregate) {
      setResults(newResults);
      return;
    }

    if (!newResults) {
      return;
    }

    setResults([...results, ...newResults]);
  }, [data]);

  return (
    <Combobox
      open={open}
      onOpenChange={(newOpen) => {
        setSearch("");
        setOpen(newOpen);
      }}
    >
      <PopoverTrigger asChild>
        <div
          className={classNames(
            inputStyle,
            "has-[>:last-child:focus]:outline-none has-[>:last-child:focus]:ring-2 has-[>:last-child:focus]:ring-custom-blue-600/25  has-[>:last-child:focus]:border-custom-blue-600",
            "cursor-pointer",
            className
          )}
        >
          <div className="flex-grow flex flex-wrap gap-2">
            {value?.map(({ id, display_label, ...data }) => (
              <Badge key={id} className="flex items-center gap-1 pr-0.5">
                {peerField ? (data[peerField]?.value ?? display_label) : display_label}

                <Button
                  size="icon"
                  variant="ghost"
                  onClick={(e) => {
                    e.stopPropagation();
                    onChange(value.filter((item) => item.id !== id));
                  }}
                  className="text-gray-500 hover:text-gray-800 h-4 w-4"
                  aria-label="Remove"
                  data-testid="remove-option"
                >
                  &times;
                </Button>
              </Badge>
            ))}
          </div>

          {loading && <Spinner className="ml-auto" />}

          <PopoverTrigger ref={ref} asChild {...props}>
            <button id={id} type="button" className="text-gray-600 outline-none w-3.5 h-3.5">
              <Icon icon="mdi:unfold-more-horizontal" />
            </button>
          </PopoverTrigger>
        </div>
      </PopoverTrigger>

      <ComboboxContent
        onOpenAutoFocus={() => {
          setOffset(0);
          setShouldAggregate(false);
          loadComboboxList();
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
          {!loading && <ComboboxEmpty>No results found</ComboboxEmpty>}

          {results
            ?.filter((node) => !!node && !value?.some((v) => v.id === node.id))
            .map((relationship) => (
              <ComboboxItem
                key={relationship.id}
                value={relationship.id}
                onSelect={() => handleSelect(relationship)}
              >
                <span className="truncate">
                  {peerField ? relationship[peerField]?.value : relationship.display_label}
                </span>
              </ComboboxItem>
            ))}

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

        <AddRelationshipAction peer={peer} onSuccess={handleSelect} />
      </ComboboxContent>
    </Combobox>
  );
});
