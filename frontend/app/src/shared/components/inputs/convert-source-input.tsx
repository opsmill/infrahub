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
        value: objectDetailsData[attribute.name]?.value ?? "-",
        label: getDisplayValue(objectDetailsData, attribute),
        source: attribute.label,
        isDefaultMatch: attribute.name === mapping.source_field_name,
      };
    });

  return (
    <Combobox open={isOpen} onOpenChange={setIsOpen}>
      <ComboboxTrigger>
        {fieldData?.value && (
          <Badge className="space-x-1">
            <span>{fieldData?.value}</span>
            <span className="font-light text-gray-700">• {fieldData.source.fieldLabel}</span>
          </Badge>
        )}
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
      return relationship.peer === peer;
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
        {fieldData?.value?.display_label && (
          <Badge className="space-x-1">
            <span>{fieldData?.value?.display_label}</span>
            <span className="font-light text-gray-700">• {fieldData.source.fieldLabel}</span>
          </Badge>
        )}
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
            source: relationship.label,
            isDefaultMatch: relationship.name === mapping.source_field_name,
          };
        }) ?? [];

      return [...acc, ...objectOptions];
    }, []);

  const handleSelect = (selectedId) => {
    const hasSelectedOption = !!fieldData.value?.includes(selectedId);

    const filteredOptions =
      fieldData.value?.filter((optionId) => {
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
        {fieldData?.value &&
          fieldData?.value?.map((nodeId) => {
            const node = availableOptions.find((nodeOption) => {
              return nodeOption.value.id === nodeId;
            })?.value;

            if (!node) {
              return null;
            }

            return (
              <Badge key={nodeId} className="space-x-1">
                <span>{getNodeLabel(node)}</span>
                <span className="font-light text-gray-700">• {fieldData.source.fieldLabel}</span>
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
              return !fieldData.value?.includes(option.value.id);
            })
            .map((option) => {
              return (
                <ComboboxItem
                  key={option.value.id}
                  value={option.value.id}
                  selectedValue={fieldData?.value}
                  onSelect={handleSelect}
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

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <ComboboxTrigger className="space-x-2">
        {fieldData.value?.map((node) => (
          <Badge key={node.id} className="flex items-center gap-1 pr-0.5">
            <span>{getNodeLabel(node)}</span>
            <span className="font-light text-gray-700">• {fieldData.source.fieldLabel}</span>

            <Button
              size="icon"
              variant="ghost"
              onClick={(e) => {
                e.stopPropagation();
                handleSelect(node);
              }}
              className="size-4 text-gray-500 hover:text-gray-800"
              aria-label="Remove"
              data-testid="remove-option"
            >
              &times;
            </Button>
          </Badge>
        ))}
      </ComboboxTrigger>

      <ComboboxContent fitTriggerWidth={false}>
        <ComboboxEmpty>No available values</ComboboxEmpty>

        {availableOptions?.map((option) => {
          return (
            <ComboboxItem
              key={option.value.id}
              value={option.value.id}
              selectedValue={fieldData?.value}
              onSelect={() => {
                handleSelect(option);
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
      </ComboboxContent>
    </Combobox>
  );
};
