import { Button } from "@/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import ObjectForm from "@/components/form/object-form";
import { PoolValue } from "@/components/form/pool-selector";
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
import { Node, RelationshipManyType } from "@/utils/getObjectItemDisplayValue";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { PopoverTriggerProps } from "@radix-ui/react-popover";
import React, { useState } from "react";
import { Badge } from "../ui/badge";
import { Tooltip } from "../ui/tooltip";

export interface RelationshipInputProps extends Omit<PopoverTriggerProps, "value" | "onChange"> {
  className?: string;
  onChange: (value: Node | PoolValue | null) => void;
  peer: string;
  value: Node | PoolValue | null;
  options?: Array<Node>;
  parent?: { name?: string; value?: string };
}

export const RelationshipInput = React.forwardRef<
  React.ElementRef<typeof PopoverTrigger>,
  RelationshipInputProps
>(({ className, value, onChange, options, peer, parent, ...props }, ref) => {
  const { schema, isNode } = useSchema(peer);
  const [open, setOpen] = React.useState(false);
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
    useLazyQuery(gql(generateRelationshipListQuery({ peer, parent })));

  const [loadPoolList, { loading: isPoolListLoading, data: poolsData }] = useLazyQuery(poolsQuery);

  const loading = isRelationshipListLoading || isPoolListLoading;

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <div className="flex gap-2">
        <ComboboxTrigger ref={ref} {...props}>
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
                {isPoolListLoading ? (
                  <Spinner className="flex justify-center m-2" />
                ) : (
                  <ComboboxEmpty>No pools found</ComboboxEmpty>
                )}
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
              </ComboboxList>
            </ComboboxContent>
          </Combobox>
        )}
      </div>

      <ComboboxContent onOpenAutoFocus={() => loadRelationshipList()}>
        <ComboboxList>
          {isRelationshipListLoading ? (
            <Spinner className="flex justify-center m-2" />
          ) : (
            <ComboboxEmpty>No results found</ComboboxEmpty>
          )}

          {!isRelationshipListLoading &&
            RelationshipListData &&
            (RelationshipListData[peer] as RelationshipManyType).edges
              .map((edge) => edge.node)
              .filter((node): node is Node => !!node)
              .map((relationship) => {
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
