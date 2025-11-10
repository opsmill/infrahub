import { Icon } from "@iconify-icon/react";
import type { PopoverTriggerProps } from "@radix-ui/react-popover";
import React, { forwardRef } from "react";

import { ACCOUNT_PERMISSION_OBJECT } from "@/config/constants";

import { Button } from "@/shared/components/buttons/button-primitive";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
} from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { Spinner } from "@/shared/components/ui/spinner";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames, debounce } from "@/shared/utils/common";

import { useObjects } from "@/entities/nodes/object/domain/get-objects.query";
import { AddRelationshipAction } from "@/entities/nodes/relationships/ui/add-relationship-action";
import type { NodeCore } from "@/entities/nodes/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

type PermissionNode = NodeCore & { identifier: { value: string } };

export interface PermissionComboboxProps extends Omit<PopoverTriggerProps, "value" | "onChange"> {
  value: PermissionNode[] | null;
  onChange: (value: PermissionNode[]) => void;
}

// This component is a temporary solution to display the permissions in a combobox
// We cannot use relationship many because the general beheviour is to use hfid/display_label
// On permission, label is it an attribute called identifier
export function PermissionCombobox({
  value,
  onChange,
  className,
  ...props
}: PermissionComboboxProps) {
  const [open, setOpen] = React.useState(false);

  const handleSelect = (relationship: PermissionNode) => {
    onChange(value ? [...value, relationship] : [relationship]);
  };

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div
          className={classNames(
            inputStyle,
            "has-[>:last-child:focus]:border-custom-blue-600 has-[>:last-child:focus]:outline-hidden has-[>:last-child:focus]:ring-2 has-[>:last-child:focus]:ring-custom-blue-600/25",
            "cursor-pointer",
            className
          )}
        >
          <div className="flex grow flex-wrap gap-2">
            {value?.map((node) => (
              <Badge key={node.id} className="flex items-center gap-1 pr-0.5">
                {node.identifier?.value}

                <Button
                  size="icon"
                  variant="ghost"
                  onClick={(e) => {
                    e.stopPropagation();
                    onChange(value.filter((item) => item.id !== node.id));
                  }}
                  className="h-4 w-4 text-gray-500 hover:text-gray-800"
                  aria-label="Remove"
                  data-testid="remove-option"
                >
                  &times;
                </Button>
              </Badge>
            ))}
          </div>

          <button
            type="button"
            className="h-3.5 w-3.5 text-gray-600 outline-hidden"
            onClick={() => setOpen(!open)}
            {...props}
          >
            <Icon icon="mdi:unfold-more-horizontal" />
          </button>
        </div>
      </PopoverTrigger>

      <ComboboxContent>
        <PermissionComboboxList onSelect={handleSelect} value={value} />
        <AddRelationshipAction peer={ACCOUNT_PERMISSION_OBJECT} onSuccess={handleSelect} />
      </ComboboxContent>
    </Combobox>
  );
}

export interface RelationshipComboboxListProps {
  value: PermissionNode[] | null;
  onSelect: (value: PermissionNode) => void;
}

export const PermissionComboboxList = forwardRef<HTMLDivElement, RelationshipComboboxListProps>(
  ({ value, onSelect }, ref) => {
    const [search, setSearch] = React.useState("");
    const { schema } = useSchema(ACCOUNT_PERMISSION_OBJECT);
    const { isPending, data, error, fetchNextPage, hasNextPage, isFetchingNextPage } = useObjects({
      schema: schema!,
      filters: search ? [{ name: "any__value", value: search }] : undefined,
    });

    if (error) return <ErrorScreen message={error.message} />;

    const setSearchDebounced = debounce(setSearch, 300);

    return (
      <ComboboxList
        ref={ref}
        onValueChange={(newValue) => setSearchDebounced(newValue)}
        shouldFilter={false}
      >
        {isPending ? (
          <Spinner className="m-2 flex justify-center" />
        ) : (
          <>
            <ComboboxEmpty>No {schema?.label ?? "results"} found</ComboboxEmpty>

            {data.pages.map((page) => {
              return page
                .filter((node) => !value?.some((v) => v.id === node.id))
                .map((n) => {
                  const node = n as unknown as PermissionNode;
                  return (
                    <ComboboxItem
                      key={node.id}
                      value={node.id}
                      selectedValue={null}
                      onSelect={() =>
                        onSelect({
                          id: node.id,
                          display_label: node.identifier.value,
                          identifier: { value: node.identifier.value },
                          __typename: node.__typename,
                        })
                      }
                    >
                      <span className="truncate">{node.identifier.value}</span>
                    </ComboboxItem>
                  );
                });
            })}
          </>
        )}

        {hasNextPage && (
          <ComboboxItem
            value="Load more"
            onSelect={() => fetchNextPage()}
            disabled={!hasNextPage || isFetchingNextPage}
            className="justify-center text-custom-blue-700"
          >
            {isFetchingNextPage ? "Loading more..." : "Load more"}
          </ComboboxItem>
        )}
      </ComboboxList>
    );
  }
);
