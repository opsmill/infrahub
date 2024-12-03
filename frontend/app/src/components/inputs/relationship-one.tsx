import { Button } from "@/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import ObjectForm from "@/components/form/object-form";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/components/ui/combobox";
import { PopoverTrigger } from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";
import { getDropdownOptions } from "@/graphql/queries/objects/dropdownOptions";
import { generateRelationshipListQuery } from "@/graphql/queries/objects/generateRelationshipListQuery";
import { useLazyQuery } from "@/hooks/useQuery";
import { useSchema } from "@/hooks/useSchema";
import { POOLS_DICTIONNARY, POOLS_PEER } from "@/screens/ipam/constants";
import { classNames } from "@/utils/common";
import { Node, RelationshipManyType } from "@/utils/getObjectItemDisplayValue";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { PopoverTriggerProps } from "@radix-ui/react-popover";
import React, { useState } from "react";
import { Badge } from "../ui/badge";
import { Tooltip } from "../ui/tooltip";

export interface RelationshipInputProps extends Omit<PopoverTriggerProps, "value" | "onChange"> {
  className?: string;
  onChange: (value: Node | null) => void;
  peer: string;
  value: Node | null;
  options?: Array<Node>;
  parent?: { name?: string; value?: string };
}

export const RelationshipInput = React.forwardRef<
  React.ElementRef<typeof PopoverTrigger>,
  RelationshipInputProps
>(({ className, value, onChange, options, peer, parent, ...props }, ref) => {
  const { schema, isNode } = useSchema(peer);
  const [open, setOpen] = React.useState(false);
  const [hasPoolsBeenOpened, setHasPoolsBeenOpened] = useState(false);

  // Check if any kind from inheritance is one of the available for pools
  const canRequestPools =
    isNode &&
    !!schema?.inherit_from?.map((from) => POOLS_PEER.includes(from))?.filter(Boolean)?.length;
  const poolPeer = canRequestPools && POOLS_DICTIONNARY[peer];
  const poolsQueryString = poolPeer ? getDropdownOptions({ kind: poolPeer }) : "query { ok }";
  const poolsQuery = gql`
    ${poolsQueryString}
  `;

  const [loadRelationshipList, { loading: isRelationshipListLoading, data }] = useLazyQuery(
    gql(generateRelationshipListQuery({ peer, parent }))
  );

  const [fetchPoolsOptions, { loading: poolsLoading, data: poolsData }] = useLazyQuery(poolsQuery);

  const loading = isRelationshipListLoading || poolsLoading;

  const handleFocus = () => {
    if (hasPoolsBeenOpened) {
      return fetchPoolsOptions();
    }

    loadRelationshipList();
  };

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <ComboboxTrigger ref={ref} {...props}>
        <span data-testid="select-value">{value?.display_label}</span>

        {loading && <Spinner className="ml-auto" />}
      </ComboboxTrigger>
      {canRequestPools && (
        <Tooltip content="Open pools options" enabled>
          <PopoverTrigger ref={ref} asChild {...props}>
            <Button
              variant={"ghost"}
              className={classNames(
                "flex items-center h-10 rounded-md p-2 ring-1 ring-inset ring-gray-300",
                "focus:outline-none disabled:cursor-not-allowed"
              )}
              data-testid="select-open-pool-option-button"
              type="button"
              onClick={() => {
                setHasPoolsBeenOpened(true);
              }}
            >
              <Icon icon={"mdi:list-box"} className="text-gray-500" />
            </Button>
          </PopoverTrigger>
        </Tooltip>
      )}

      <ComboboxContent onOpenAutoFocus={() => loadRelationshipList()}>
        <ComboboxList>
          {loading ? (
            <Spinner className="flex justify-center m-2" />
          ) : (
            <ComboboxEmpty>No results found</ComboboxEmpty>
          )}

          {!loading &&
            !hasPoolsBeenOpened &&
            data &&
            (data[peer] as RelationshipManyType).edges
              .map((edge) => edge.node)
              .filter((node): node is Node => !!node && value?.id !== node.id)
              .map((relationship) => {
                return (
                  <ComboboxItem
                    key={relationship.id}
                    value={relationship.id}
                    onSelect={() => {
                      onChange(relationship);
                      setOpen(false);
                    }}
                  >
                    <span className="truncate">{relationship.display_label}</span>
                  </ComboboxItem>
                );
              })}

          {!loading &&
            hasPoolsBeenOpened &&
            poolsData &&
            (poolsData[poolPeer] as RelationshipManyType).edges
              .map((edge) => edge.node)
              .filter((node): node is Node => !!node && value?.id !== node.id)
              .map((relationship) => {
                return (
                  <ComboboxItem
                    key={relationship.id}
                    value={relationship.id}
                    onSelect={() => {
                      onChange(relationship);
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

export interface AddRelationshipActionProps {
  peer: string;
  onSuccess?: (newObject: Node) => void;
}

const AddRelationshipAction: React.FC<AddRelationshipActionProps> = ({ peer, onSuccess }) => {
  const { schema } = useSchema(peer);
  const [open, setOpen] = useState(false);

  if (!schema) return null;

  return (
    <div className="p-2 pt-0">
      <Button
        className="w-full bg-custom-blue-700/10 border border-custom-blue-700/20 text-custom-blue-700 enabled:hover:bg-custom-blue-700/20"
        onClick={() => setOpen(!open)}
      >
        + Add new {schema.label}
      </Button>

      <SlideOver
        title={
          <SlideOverTitle
            schema={schema}
            currentObjectLabel="New"
            title={`Create ${schema.label}`}
            subtitle={schema.description}
          />
        }
        offset={1}
        open={open}
        setOpen={setOpen}
      >
        <ObjectForm
          kind={peer}
          onSuccess={({ object }) => {
            setOpen(false);
            if (!onSuccess) return;

            const newNode: Node = {
              id: object.id,
              display_label: object.display_label,
              __typename: peer,
            };
            onSuccess(newNode);
          }}
          onCancel={() => setOpen(false)}
          data-testid="new-object-form"
        />
      </SlideOver>
    </div>
  );
};
