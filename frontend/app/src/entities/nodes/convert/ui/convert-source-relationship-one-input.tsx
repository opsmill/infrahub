import React from "react";

import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";

import type {
  ConvertSourceRelationshipInputProps,
  RelationshipOneSourceOption,
} from "@/entities/nodes/convert/types";
import type { Node } from "@/entities/nodes/getObjectItemDisplayValue";

export const ConvertSourceRelationshipOneInput = ({
  sourceObject,
  sourceSchema,
  mapping,
  value,
  onChange,
  peer,
  className,
}: ConvertSourceRelationshipInputProps) => {
  const [open, setOpen] = React.useState(false);

  const fieldData = value;

  const availableOptions: Array<RelationshipOneSourceOption> = (sourceSchema.relationships ?? [])
    .filter((relationship) => relationship.peer === peer)
    .map((relationship) => {
      const relationshipData = sourceObject[relationship.name];
      return {
        value: relationshipData && "node" in relationshipData ? relationshipData.node : null,
        source: {
          type: "source",
          label: relationship.label ?? relationship.name,
          name: relationship.name,
        },
        isDefaultMatch: relationship.name === mapping?.source_field_name,
      };
    });

  const currentOption = availableOptions?.find((nodeOption) => {
    return nodeOption.source.name === fieldData?.source?.name;
  });

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <ComboboxTrigger className={className}>
        {currentOption && (
          <Badge className="space-x-1">
            <span>{currentOption?.value?.display_label || "-"}</span>
            <span className="font-light text-gray-700">• {currentOption?.source?.label}</span>
          </Badge>
        )}
      </ComboboxTrigger>
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
                      label: option.source.label,
                      name: option.source.name,
                      node: option.value,
                    },
                    value: option.value as Node | null,
                  });
                  setOpen(false);
                }}
              >
                <div className="flex grow items-center justify-between">
                  <span className="grow">{option.value?.display_label || "-"}</span>

                  <div className="space-x-2">
                    {option.isDefaultMatch && <Badge variant={"blue-outline"}>Matched</Badge>}

                    <Badge variant={"gray-outline"}>{option.source?.label}</Badge>
                  </div>
                </div>
              </ComboboxItem>
            );
          })}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
};
