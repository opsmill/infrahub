import React from "react";
import { isDeepEqual } from "remeda";

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
import type { NodeAttribute } from "@/entities/nodes/types";
import type { AttributeSchema } from "@/entities/schema/types";

interface ConvertSourceAttributeInputProps extends ConvertSourceInputProps {
  attribute: AttributeSchema;
}

export const ConvertSourceAttributeInput = ({
  sourceObject,
  sourceSchema,
  mapping,
  attribute,
  value,
  onChange,
  ...props
}: ConvertSourceAttributeInputProps) => {
  const [open, setOpen] = React.useState(false);

  const availableOptions: Array<AttributeSourceOption> = (sourceSchema.attributes ?? [])
    .filter((sourceAttribute) => {
      if (attribute.kind === "Text" && attribute.enum) {
        return isDeepEqual(attribute.enum, sourceAttribute.enum);
      }

      if (attribute.kind === "Dropdown") {
        return isDeepEqual(attribute.choices, sourceAttribute.choices);
      }

      return sourceAttribute.kind === attribute.kind && !sourceAttribute.enum;
    })
    .map((attribute) => {
      const attrData = sourceObject[attribute.name] as NodeAttribute | undefined;
      return {
        value: attrData ? attrData.value : null,
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
    return option.source.name === value?.source?.name;
  });

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <ComboboxTrigger {...props}>
        {currentOption && (
          <SourceOptionValue
            optionLabel={currentOption.label}
            sourceFieldName={currentOption.source?.label}
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
                selectedValue={value?.source?.name}
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
