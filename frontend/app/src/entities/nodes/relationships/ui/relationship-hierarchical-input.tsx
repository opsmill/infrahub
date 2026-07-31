import { Icon } from "@iconify-icon/react";
import { Button } from "@infrahub/ui";
import React from "react";

import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxTrigger,
  type ComboboxTriggerProps,
} from "@/shared/components/ui/combobox";
import {
  PopoverTabs,
  PopoverTabsContent,
  PopoverTabsList,
  PopoverTabsTrigger,
  PopoverTrigger,
} from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import type { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { AddRelationshipAction } from "@/entities/nodes/relationships/ui/add-relationship-action";
import {
  RelationshipComboboxList,
  type RelationshipComboboxListProps,
} from "@/entities/nodes/relationships/ui/relationship-combobox-list";
import { RelationshipHierarchicalComboboxList } from "@/entities/nodes/relationships/ui/relationship-hierarchical-combobox-list";
import type { NodeFieldsWithMetadata } from "@/entities/nodes/types";

export interface RelationshipHierarchicalContentProps extends RelationshipComboboxListProps {
  // The tree explorer browses the peer's own hierarchy and cannot honor an external filterQuery,
  // so it is dropped when a filter must be enforced (e.g. common_parent).
  hideExplore?: boolean;
  // Pre-fills the "Add new" create form so a created peer satisfies an enforced filter.
  addNewInitialObject?: NodeFieldsWithMetadata;
}

export const RelationshipHierarchicalContent = ({
  hideExplore,
  addNewInitialObject,
  ...props
}: RelationshipHierarchicalContentProps) => {
  if (hideExplore) {
    return (
      <ComboboxContent>
        <RelationshipComboboxList {...props} />
        <AddRelationshipAction {...props} initialObject={addNewInitialObject} />
      </ComboboxContent>
    );
  }

  return (
    <ComboboxContent>
      <PopoverTabs defaultValue="list">
        <PopoverTabsList className="mt-1">
          <PopoverTabsTrigger value="list">All</PopoverTabsTrigger>
          <PopoverTabsTrigger value="tree">Explore</PopoverTabsTrigger>
        </PopoverTabsList>

        <PopoverTabsContent value="list">
          <RelationshipComboboxList {...props} />
          <AddRelationshipAction {...props} initialObject={addNewInitialObject} />
        </PopoverTabsContent>

        <PopoverTabsContent value="tree">
          <RelationshipHierarchicalComboboxList {...props} />
        </PopoverTabsContent>
      </PopoverTabs>
    </ComboboxContent>
  );
};

export interface RelationshipHierarchicalInputProps
  extends Omit<ComboboxTriggerProps, "value" | "onChange"> {
  ref?: React.Ref<HTMLButtonElement>;
  onChange?: (value: RelationshipNode | null) => void;
  value?: RelationshipNode | null;
  peer: string;
  filterQuery?: Record<string, string | number | boolean | string[]>;
  hideExplore?: boolean;
  addNewInitialObject?: NodeFieldsWithMetadata;
  enforceFilterQueryOnIdSearch?: boolean;
}

export const RelationshipHierarchicalInput = ({
  ref,
  value,
  onChange,
  peer,
  filterQuery,
  hideExplore,
  addNewInitialObject,
  enforceFilterQueryOnIdSearch,
  ...props
}: RelationshipHierarchicalInputProps) => {
  const [open, setOpen] = React.useState(false);

  const handleSelect = (relationship: RelationshipNode) => {
    onChange?.(relationship.id === value?.id ? null : relationship);
    setOpen(false);
  };

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <ComboboxTrigger ref={ref} {...props}>
        {value ? getNodeLabel(value) : ""}
      </ComboboxTrigger>

      <RelationshipHierarchicalContent
        peer={peer}
        onSelect={handleSelect}
        value={value}
        filterQuery={filterQuery}
        hideExplore={hideExplore}
        addNewInitialObject={addNewInitialObject}
        enforceFilterQueryOnIdSearch={enforceFilterQueryOnIdSearch}
      />
    </Combobox>
  );
};

export interface RelationshipHierarchicalManyInputProps
  extends Omit<ComboboxTriggerProps, "value" | "onChange"> {
  ref?: React.Ref<HTMLButtonElement>;
  onChange: (value: RelationshipNode[]) => void;
  value?: RelationshipNode[] | null;
  peer: string;
  filterQuery?: Record<string, string | number | boolean | string[]>;
  hideExplore?: boolean;
  addNewInitialObject?: NodeFieldsWithMetadata;
  enforceFilterQueryOnIdSearch?: boolean;
}

export const RelationshipHierarchicalManyInput = ({
  ref,
  value,
  onChange,
  peer,
  className,
  filterQuery,
  hideExplore,
  addNewInitialObject,
  enforceFilterQueryOnIdSearch,
  ...props
}: RelationshipHierarchicalManyInputProps) => {
  const [open, setOpen] = React.useState(false);

  const handleSelect = (relationship: Node) => {
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
                {getNodeLabel(node)}

                <Button
                  size="xs"
                  shape="circle"
                  variant="ghost"
                  onPress={() => {
                    onChange(value?.filter((item) => item.id !== node.id));
                  }}
                  className="h-4 w-4 text-gray-500 data-hovered:text-gray-800"
                  aria-label={`Remove ${getNodeLabel(node)}`}
                  data-testid="remove-option"
                >
                  &times;
                </Button>
              </Badge>
            ))}
          </div>

          <PopoverTrigger ref={ref} asChild {...props}>
            <button
              type="button"
              className="h-3.5 w-3.5 text-gray-600 outline-hidden"
              aria-label={`Open ${peer}`}
            >
              <Icon icon="mdi:unfold-more-horizontal" />
            </button>
          </PopoverTrigger>
        </div>
      </PopoverTrigger>

      <RelationshipHierarchicalContent
        peer={peer}
        onSelect={handleSelect}
        filterItem={(node) => !value?.some((v) => v.id === node.id)}
        filterQuery={filterQuery}
        hideExplore={hideExplore}
        addNewInitialObject={addNewInitialObject}
        enforceFilterQueryOnIdSearch={enforceFilterQueryOnIdSearch}
      />
    </Combobox>
  );
};
