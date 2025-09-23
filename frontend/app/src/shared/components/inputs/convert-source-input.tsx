import { useState } from "react";

import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";

import { getDisplayValue } from "@/entities/nodes/getObjectItemDisplayValue";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeObject } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";

import { Button } from "../buttons/button-primitive";

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
      return attribute.kind === kind;
    })
    .map((attribute) => {
      return {
        value: objectDetailsData[attribute.name]?.value,
        label: getDisplayValue(objectDetailsData, attribute) || "-",
        source: {
          label: attribute.label,
          name: attribute.name,
        },
        isDefaultMatch: attribute.name === mapping.source_field_name,
      };
    });

  const currentOption = availableOptions?.find((option) => {
    return option.source.name === fieldData.value.name;
  });

  return (
    <Combobox open={isOpen} onOpenChange={setIsOpen}>
      <ComboboxTrigger>
        {currentOption && (
          <Badge className="space-x-1">
            <span>{currentOption.label}</span>
            <span className="font-light text-gray-700">• {currentOption.source?.label}</span>
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
                selectedValue={fieldData.value?.name}
                onSelect={() => {
                  onSelect(option);
                  setIsOpen(false);
                }}
              >
                <div className="flex grow items-center justify-between">
                  <span className="grow">{option.label}</span>

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
      return relationship.peer === peer;
    })
    .map((relationship) => {
      return {
        value: objectDetailsData[relationship.name]?.node,
        source: {
          label: relationship.label,
          name: relationship.name,
        },
        isDefaultMatch: relationship.name === mapping.source_field_name,
      };
    });

  const currentOption = availableOptions?.find((nodeOption) => {
    return nodeOption.source.name === fieldData.value?.name;
  });

  return (
    <Combobox open={isOpen} onOpenChange={setIsOpen}>
      <ComboboxTrigger>
        <Badge className="space-x-1">
          <span>{currentOption?.value?.display_label || "-"}</span>
          <span className="font-light text-gray-700">• {currentOption?.source?.label}</span>
        </Badge>
      </ComboboxTrigger>
      <ComboboxContent fitTriggerWidth={false}>
        <ComboboxList>
          <ComboboxEmpty>No available values</ComboboxEmpty>

          {availableOptions?.map((option) => {
            return (
              <ComboboxItem
                key={option.source.name}
                value={option.source.name}
                selectedValue={fieldData.value?.name}
                onSelect={() => {
                  onSelect(option);
                  setIsOpen(false);
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

export const ConvertSourceRelationshipManyInput = ({
  objectDetailsData,
  sourceSchema,
  mapping,
  fieldData,
  onSelect,
  peer,
}: ConvertSourceRelationshipInputParams) => {
  const [open, setOpen] = useState(false);

  const availableOptions = sourceSchema?.relationships
    ?.filter((relationship) => {
      return relationship.peer === peer;
    })
    .reduce((acc, relationship) => {
      const objectOptions =
        objectDetailsData[relationship.name]?.edges?.map((edge) => {
          return {
            value: edge.node,
            label: edge.node.display_label,
            source: {
              label: relationship.label,
              name: relationship.name,
            },
            isDefaultMatch: relationship.name === mapping.source_field_name,
          };
        }) ?? [];

      return [...acc, ...objectOptions];
    }, []);

  const handleSelect = (selectedId) => {
    const hasSelectedOption = !!fieldData.value?.includes(selectedId);

    const filteredOptions =
      fieldData.value?.value?.filter((optionId) => {
        return selectedId !== optionId;
      }) ?? [];

    if (hasSelectedOption) {
      onSelect(filteredOptions);
    } else {
      onSelect([...filteredOptions, selectedId]);
    }
  };

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <ComboboxTrigger className="space-x-2">
        {fieldData?.value?.value &&
          fieldData?.value?.value?.map((nodeId) => {
            const node = availableOptions.find((nodeOption) => {
              return nodeOption.value?.id === nodeId;
            })?.value;

            if (!node) {
              return null;
            }

            return (
              <Badge key={nodeId} className="space-x-1">
                <span>{getNodeLabel(node)}</span>
                <span className="font-light text-gray-700">• {fieldData.value?.label}</span>
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleSelect(nodeId);
                  }}
                  className="size-4 text-gray-500 hover:text-gray-800"
                  aria-label="Remove"
                  data-testid="remove-option"
                >
                  &times;
                </Button>
              </Badge>
            );
          })}
      </ComboboxTrigger>
      <ComboboxContent fitTriggerWidth={false}>
        <ComboboxList>
          <ComboboxEmpty>No available values</ComboboxEmpty>

          {availableOptions
            ?.filter((option) => {
              return !fieldData.value?.value?.includes(option.value?.value?.id);
            })
            .map((option) => {
              return (
                <ComboboxItem
                  key={option.value?.id}
                  value={option.value?.id}
                  selectedValue={fieldData?.value?.value}
                  onSelect={handleSelect}
                >
                  <div className="flex grow items-center justify-between">
                    <span className="grow">{option.label}</span>

                    <div className="space-x-2">
                      {option.isDefaultMatch && <Badge variant={"blue-outline"}>Matched</Badge>}

                      <Badge variant={"gray-outline"}>{option.source.name}</Badge>
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
