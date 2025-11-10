import React from "react";

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
import {
  SourceOptionItem,
  SourceOptionValue,
} from "@/entities/nodes/convert/ui/source-option-item";
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
          <SourceOptionValue
            optionLabel={currentOption?.value?.display_label || "-"}
            sourceFieldName={currentOption.source?.label}
          />
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
                      name: option.source.name,
                    },
                    value: option.value as Node | null,
                  });
                  setOpen(false);
                }}
              >
                <SourceOptionItem
                  optionLabel={option.value?.display_label || "-"}
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
