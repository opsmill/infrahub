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
  AttributeSourceOption,
  ConvertSourceInputProps,
} from "@/entities/nodes/convert/types";
import {
  SourceOptionItem,
  SourceOptionValue,
} from "@/entities/nodes/convert/ui/source-option-item";
import { getDisplayValue } from "@/entities/nodes/getObjectItemDisplayValue";
import type { AttributeSchema } from "@/entities/schema/types";

interface ConvertSourceAttributeComboboxProps extends ConvertSourceInputProps {
  attribute: AttributeSchema;
}

export const ConvertSourceAttributeCombobox = ({
  sourceObject,
  sourceSchema,
  mapping,
  attribute,
  value,
  onChange,
  ...props
}: ConvertSourceAttributeComboboxProps) => {
  const [open, setOpen] = React.useState(false);

  const fieldData = value;

  const availableOptions: Array<AttributeSourceOption> = (sourceSchema.attributes ?? [])
    .filter((sourceAttribute) => {
      if (attribute.kind === "Text" && attribute.enum) {
        const sortedAttributeEnumOptions = attribute.enum.sort();
        const sortedSourceEnumOptions = sourceAttribute?.enum?.sort();
        const areEqual =
          JSON.stringify(sortedAttributeEnumOptions) === JSON.stringify(sortedSourceEnumOptions);

        return areEqual;
      }

      if (attribute.kind === "Dropdown") {
        const sortedAttributeDropdownOptions = attribute?.choices?.sort(
          (itemA, itemB) => itemA.name - itemB.name
        );
        const sortedSourceDropdownOptions = sourceAttribute?.choices?.sort(
          (itemA, itemB) => itemA.name - itemB.name
        );
        const areEqual =
          JSON.stringify(sortedAttributeDropdownOptions) ===
          JSON.stringify(sortedSourceDropdownOptions);

        return areEqual;
      }

      return sourceAttribute.kind === attribute.kind && !sourceAttribute.enum;
    })
    .map((attribute) => {
      const attrData = sourceObject[attribute.name];
      return {
        value: attrData && "value" in attrData ? attrData.value : null,
        label: getDisplayValue(sourceObject, attribute) || "-",
        source: {
          type: "source",
          label: attribute.label ?? attribute.name,
          name: attribute.name,
        },
        isDefaultMatch: attribute.name === mapping?.source_field_name,
      };
    });

  const currentOption = availableOptions?.find((option) => {
    return option.source.name === fieldData?.source?.name;
  });

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <ComboboxTrigger {...props}>
        {currentOption && (
          <SourceOptionValue
            optionLabel={currentOption.label}
            sourceLabel={currentOption.source?.label}
          />
        )}
      </ComboboxTrigger>

      <ComboboxContent fitTriggerWidth={false}>
        <ComboboxList>
          <ComboboxEmpty>No available attributes</ComboboxEmpty>

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
                    value: option.value,
                  });
                  setOpen(false);
                }}
              >
                <SourceOptionItem
                  optionLabel={option.label || "-"}
                  isDefaultMatch={option.isDefaultMatch}
                  sourceLabel={option.source?.label}
                />
              </ComboboxItem>
            );
          })}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
};
