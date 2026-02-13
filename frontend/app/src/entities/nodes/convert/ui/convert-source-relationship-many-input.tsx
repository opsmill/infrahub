import { Icon } from "@iconify-icon/react";
import React from "react";

import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
} from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import type {
  ConvertSourceRelationshipInputProps,
  RelationshipManySourceOption,
} from "@/entities/nodes/convert/types";
import {
  SourceOptionItem,
  SourceOptionValue,
} from "@/entities/nodes/convert/ui/source-option-item";
import type { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeCore, NodeRelationshipMany } from "@/entities/nodes/types";

export const ConvertSourceRelationshipManyInput = ({
  sourceObject,
  sourceSchema,
  mapping,
  peer,
  className,
  value,
  onChange,
}: ConvertSourceRelationshipInputProps) => {
  const [open, setOpen] = React.useState(false);

  const fieldData = value;

  const availableOptions: Array<RelationshipManySourceOption> = (sourceSchema.relationships ?? [])
    .filter((relationship) => {
      // Get all relationships that use the same peer (can be cardinality one and many)
      return relationship.peer === peer && relationship.cardinality === "many";
    })
    .reduce<Array<RelationshipManySourceOption>>((acc, relationship) => {
      const relationshipData = sourceObject[relationship.name] as NodeRelationshipMany | undefined;
      const objectsOptions = relationshipData
        ? relationshipData.edges.map((edge) => edge.node).filter((n) => !!n)
        : [];

      const option: RelationshipManySourceOption = {
        source: {
          type: "source",
          name: relationship.name,
          label: relationship.label ?? relationship.name,
        },
        value: objectsOptions,
        isDefaultMatch: relationship.name === mapping?.source_field_name,
      };

      return [...acc, option];
    }, []);

  const currentOption = availableOptions?.find((nodeOption) => {
    return nodeOption.source.name === fieldData?.source?.name;
  });

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div
          className={classNames(
            inputStyle,
            "has-[>:last-child:focus]:border-custom-blue-600 has-[>:last-child:focus]:outline-hidden has-[>:last-child:focus]:ring-2 has-[>:last-child:focus]:ring-custom-blue-600/25",
            "w-full cursor-pointer",
            "flex justify-between",
            className
          )}
        >
          <div className="space-x-2">
            {currentOption?.source?.name && currentOption?.value && (
              <SourceOptionValue
                optionLabel={
                  currentOption?.value
                    .map((node: NodeCore) => {
                      return getNodeLabel(node);
                    })
                    .join(" - ") || "-"
                }
                sourceFieldName={currentOption?.source?.label}
              />
            )}
          </div>

          <button type="button" className="h-3.5 w-3.5 text-gray-600 outline-hidden">
            <Icon icon="mdi:unfold-more-horizontal" />
          </button>
        </div>
      </PopoverTrigger>

      <ComboboxContent fitTriggerWidth={false}>
        <ComboboxList>
          <ComboboxEmpty>No available values</ComboboxEmpty>

          {availableOptions?.map((option) => {
            return (
              <ComboboxItem
                key={option.source.name}
                value={option.source.name}
                selectedValue={fieldData?.source?.name}
                onSelect={() => {
                  onChange({
                    source: {
                      type: "source",
                      name: option.source.name,
                    },
                    value: (option.value as Array<Node> | null) ?? null,
                  });
                  setOpen(false);
                }}
              >
                <SourceOptionItem
                  optionLabel={
                    option?.value
                      ?.map((node) => {
                        return getNodeLabel(node);
                      })
                      .join(" - ") || "-"
                  }
                  isDefaultMatch={option.isDefaultMatch}
                  sourceFieldName={option.source?.label}
                />
              </ComboboxItem>
            );
          })}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
};
