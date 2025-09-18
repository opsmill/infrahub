import { useState } from "react";

import { ModelSchema } from "@/entities/schema/types";
import { NodeObject } from "@/entities/nodes/types";
import { getDisplayValue } from "@/entities/nodes/getObjectItemDisplayValue";

import { Badge } from "../ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "../ui/combobox";

interface Mapping {
  is_mandatory: boolean;
  relationship_cardinality: string;
  source_field_name: string;
}

interface ConvertSourceInputParams {
  objectDetailsData: NodeObject;
  sourceSchema: ModelSchema;
  fieldData: any;
  onSelect: (option: any) => void;
  mapping: Mapping;
}

interface ConvertSourceAttributeInputParams extends ConvertSourceInputParams {
  kind: string;
}

interface ConvertSourceRelationshipInputParams extends ConvertSourceInputParams {
  peer: string;
}

export const ConvertSourceAttributeInput = ({
  objectDetailsData,
  sourceSchema,
  mapping,
  fieldData,
  onSelect,
  kind,
}: ConvertSourceAttributeInputParams) => {
  const [isOpen, setIsOpen] = useState(false);

  const availableOptions = sourceSchema?.attributes
    ?.filter((attribute) => {
      return attribute.kind === kind && !!objectDetailsData[attribute.name]?.value;
    })
    .map((attribute) => {
      return {
        value: objectDetailsData[attribute.name]?.value,
        label: getDisplayValue(objectDetailsData, attribute),
        source: attribute.label,
        isDefaultMatch: attribute.name === mapping.source_field_name,
      };
    });

  return (
    <Combobox open={isOpen} onOpenChange={setIsOpen}>
      <ComboboxTrigger>
        {
          fieldData?.value && <Badge className="space-x-1">
            <span>{fieldData?.value}</span>
            <span className="text-gray-700 font-light">• {fieldData.source.fieldLabel}</span>
          </Badge>
        }
      </ComboboxTrigger>
      <ComboboxContent fitTriggerWidth={false}>
        <ComboboxList>
          <ComboboxEmpty>No available values</ComboboxEmpty>

          {availableOptions?.map((option) => {
            return (
              <ComboboxItem
                key={option.value}
                value={option.value}
                selectedValue={fieldData?.value}
                onSelect={() => {
                  onSelect(option);
                  setIsOpen(false);
                }}
              >
                <div className="flex grow items-center justify-between">
                  <span className="grow">{option.label}</span>

                  <div className="space-x-2">
                    {option.isDefaultMatch && <Badge variant={"blue-outline"}>Matched</Badge>}

                    <Badge variant={"gray-outline"}>{option.source}</Badge>
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

export const ConvertSourceRelationshipOneInput = ({
  objectDetailsData,
  sourceSchema,
  mapping,
  fieldData,
  onSelect,
  peer,
}: ConvertSourceRelationshipInputParams) => {
  const [isOpen, setIsOpen] = useState(false);

  const availableOptions = sourceSchema?.relationships
  ?.filter((relationship) => {
    return relationship.peer === peer && !!objectDetailsData[relationship.name]?.node?.id;
  })
  .map((relationship) => {
    return {
      value: objectDetailsData[relationship.name]?.node,
      label: getDisplayValue(objectDetailsData, relationship),
      source: relationship.label,
      isDefaultMatch: relationship.name === mapping.source_field_name,
    };
  });

  return (
    <Combobox open={isOpen} onOpenChange={setIsOpen}>
      <ComboboxTrigger>
        {
          fieldData?.value?.display_label && <Badge className="space-x-1">
            <span>{fieldData?.value?.display_label}</span>
            <span className="text-gray-700 font-light">• {fieldData.source.fieldLabel}</span>
          </Badge>
        }
      </ComboboxTrigger>
      <ComboboxContent fitTriggerWidth={false}>
        <ComboboxList>
          <ComboboxEmpty>No available values</ComboboxEmpty>

          {availableOptions?.map((option) => {
            return (
              <ComboboxItem
                key={option.value}
                value={option.value}
                selectedValue={fieldData?.value}
                onSelect={() => {
                  onSelect(option);
                  setIsOpen(false);
                }}
              >
                <div className="flex grow items-center justify-between">
                  <span className="grow">{option.label}</span>

                  <div className="space-x-2">
                    {option.isDefaultMatch && <Badge variant={"blue-outline"}>Matched</Badge>}

                    <Badge variant={"gray-outline"}>{option.source}</Badge>
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