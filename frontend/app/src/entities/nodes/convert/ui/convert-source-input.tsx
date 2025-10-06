import { Icon } from "@iconify-icon/react";
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
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import type { ConvertFieldMapping, ConvertFormFieldValue } from "@/entities/nodes/convert/types";
import { getDisplayValue } from "@/entities/nodes/getObjectItemDisplayValue";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeCore, NodeObject } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";

interface ConvertSourceInputProps {
  sourceObject: NodeObject;
  sourceSchema: ModelSchema;
  mapping?: ConvertFieldMapping;
  className?: string;
  value: ConvertFormFieldValue;
  onChange: (value: ConvertFormFieldValue) => void;
}

interface ConvertSourceOption {
  source: {
    type: "source";
    name: string;
    label: string | null | undefined;
  };
  isDefaultMatch: boolean;
}

interface AttributeSourceOption extends ConvertSourceOption {
  value: string | string[] | number | boolean | null;
  label: React.ReactNode;
}

interface RelationshipOneSourceOption extends ConvertSourceOption {
  value: NodeCore | null;
}

interface RelationshipManySourceOption extends ConvertSourceOption {
  value: Array<NodeCore> | null;
}

interface ConvertSourceAttributeComboboxProps extends ConvertSourceInputProps {
  kind: string;
}

export const ConvertSourceAttributeCombobox = ({
  sourceObject,
  sourceSchema,
  mapping,
  value,
  onChange,
  kind,
  ...props
}: ConvertSourceAttributeComboboxProps) => {
  const [open, setOpen] = React.useState(false);

  const fieldData = value;

  const availableOptions: Array<AttributeSourceOption> = (sourceSchema.attributes ?? [])
    .filter((attribute) => attribute.kind === kind)
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
          <Badge className="space-x-1">
            <span>{currentOption.label}</span>
            <span className="font-light text-gray-700">• {currentOption.source?.label}</span>
          </Badge>
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

interface ConvertSourceRelationshipInputProps extends ConvertSourceInputProps {
  peer: string;
}

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
                    value: option.value,
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
      const relationshipData = sourceObject[relationship.name];
      const objectsOptions =
        relationshipData && "edges" in relationshipData && Array.isArray(relationshipData.edges)
          ? relationshipData.edges.map((edge) => edge.node)
          : [];

      const option = {
        source: {
          type: "source",
          name: relationship.name,
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
              <Badge className="space-x-1">
                <span>
                  {currentOption?.value
                    .map((node: NodeCore) => {
                      return getNodeLabel(node);
                    })
                    .join(" - ") || "-"}
                </span>
                <span className="font-light text-gray-700">• {currentOption?.source?.label}</span>
              </Badge>
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
                    value: option.value?.map((node) => {
                      return node;
                    }),
                  });
                  setOpen(false);
                }}
              >
                <div className="flex grow items-center justify-between">
                  <span className="grow">
                    {option?.value
                      ?.map((node) => {
                        return getNodeLabel(node);
                      })
                      .join(" - ") || "-"}
                  </span>

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
