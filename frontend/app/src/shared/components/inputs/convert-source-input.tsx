import { Icon } from "@iconify-icon/react";
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
import { classNames } from "@/shared/utils/common";

import { getDisplayValue } from "@/entities/nodes/getObjectItemDisplayValue";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeObject } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";

import { Button } from "../buttons/button-primitive";
import { PopoverTrigger } from "../ui/popover";
import { inputStyle } from "../ui/style";

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
    return option.source.name === fieldData?.source?.name;
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
                selectedValue={fieldData.source?.name}
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
    return nodeOption.source.name === fieldData.source?.name;
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
                selectedValue={fieldData.source?.name}
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
      // Get all relationships that use the same peer (can be cardinality one and many)
      return relationship.peer === peer;
    })
    .reduce((acc, relationship) => {
      // Get available options if values are used in cardinality one
      if (objectDetailsData[relationship.name]?.node) {
        const objectOption = {
          value: objectDetailsData[relationship.name]?.node,
          label: objectDetailsData[relationship.name]?.node.display_label,
          source: {
            label: relationship.label,
            name: relationship.name,
          },
          isDefaultMatch: relationship.name === mapping.source_field_name,
        };

        return [...acc, objectOption];
      }

      // Get available options if values are used in cardinality many
      if (objectDetailsData[relationship.name]?.edges) {
        const objectsOptions =
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

        return [...acc, ...objectsOptions];
      }

      return acc;
    }, []);

  const handleSelect = (selectedId, selectedSource) => {
    const hasSelectedOption = !!fieldData.value?.includes(selectedId);

    const filteredOptions =
      fieldData.value?.filter((optionId) => {
        return selectedId !== optionId;
      }) ?? [];

    if (hasSelectedOption) {
      const cleanedSourceMapping = fieldData.source.values
        ? Object.entries(fieldData.source.values).reduce((acc, [nodeId, nodeSource]) => {
            if (nodeId === selectedId) {
              return acc;
            }

            return {
              ...acc,
              [nodeId]: nodeSource,
            };
          }, {})
        : {};

      onSelect(filteredOptions, cleanedSourceMapping);
    } else {
      const newSourceMapping = {
        ...fieldData.source.values,
        [selectedId]: selectedSource,
      };
      onSelect([...filteredOptions, selectedId], newSourceMapping);
    }
  };

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div
          className={classNames(
            inputStyle,
            "has-[>:last-child:focus]:border-custom-blue-600 has-[>:last-child:focus]:outline-hidden has-[>:last-child:focus]:ring-2 has-[>:last-child:focus]:ring-custom-blue-600/25",
            "w-full cursor-pointer",
            "flex justify-between"
          )}
        >
          <div className="space-x-2">
            {fieldData?.value?.map((nodeId: string) => {
              const node = availableOptions.find((nodeOption) => {
                return nodeOption.value?.id === nodeId;
              })?.value;

              if (!node) {
                return null;
              }

              return (
                <Badge key={nodeId} className="space-x-1">
                  <span>{getNodeLabel(node)}</span>
                  <span className="font-light text-gray-700">
                    • {fieldData.source?.values?.[nodeId].label}
                  </span>
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
          </div>

          <button type="button" className="h-3.5 w-3.5 text-gray-600 outline-hidden">
            <Icon icon="mdi:unfold-more-horizontal" />
          </button>
        </div>
      </PopoverTrigger>
      <ComboboxContent fitTriggerWidth={false}>
        <ComboboxList>
          <ComboboxEmpty>No available values</ComboboxEmpty>

          {availableOptions
            ?.filter((option) => {
              return !fieldData.value?.includes(option?.value?.id);
            })
            .map((option) => {
              return (
                <ComboboxItem
                  key={option.value?.id}
                  value={option.value?.id}
                  selectedValue={fieldData?.value?.id}
                  onSelect={(newId) => {
                    handleSelect(newId, { name: option.source.name, label: option.source.label });
                  }}
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
