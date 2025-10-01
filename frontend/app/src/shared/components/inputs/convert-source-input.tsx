import { Icon } from "@iconify-icon/react";
import { type ReactNode, useState } from "react";

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
import type { NodeCore, NodeObject } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";

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
  field: any;
  mapping: Mapping;
}

interface ConvertSourceAttributeInputParams extends ConvertSourceInputParams {
  kind: string;
}

interface ConvertSourceRelationshipInputParams extends ConvertSourceInputParams {
  peer: string;
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
  label: ReactNode;
}

interface RelationshipOneSourceOption extends ConvertSourceOption {
  value: NodeCore | null;
}

interface RelationshipManySourceOption extends ConvertSourceOption {
  value: Array<NodeCore> | null;
}

export const ConvertSourceAttributeInput = ({
  objectDetailsData,
  sourceSchema,
  mapping,
  field,
  kind,
}: ConvertSourceAttributeInputParams) => {
  const [open, setOpen] = useState(false);

  const fieldData = field.value;

  const availableOptions: Array<AttributeSourceOption> =
    "attributes" in sourceSchema && sourceSchema.attributes
      ? sourceSchema.attributes
          .filter((attribute) => {
            return attribute.kind === kind;
          })
          .map((attribute) => {
            const attrData = objectDetailsData[attribute.name];
            return {
              value: attrData && "value" in attrData ? attrData.value : null,
              label: getDisplayValue(objectDetailsData, attribute) || "-",
              source: {
                type: "source",
                label: attribute.label ?? attribute.name,
                name: attribute.name,
              },
              isDefaultMatch: attribute.name === mapping.source_field_name,
            };
          })
      : [];

  const currentOption = availableOptions?.find((option) => {
    return option.source.name === fieldData?.source?.name;
  });

  return (
    <Combobox open={open} onOpenChange={setOpen}>
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
                selectedValue={fieldData?.source?.name}
                onSelect={() => {
                  field.onChange({
                    source: {
                      type: "source",
                      label: option.source.label,
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

export const ConvertSourceRelationshipOneInput = ({
  objectDetailsData,
  sourceSchema,
  mapping,
  field,
  peer,
}: ConvertSourceRelationshipInputParams) => {
  const [open, setOpen] = useState(false);

  const fieldData = field.value;

  const availableOptions: Array<RelationshipOneSourceOption> =
    "relationships" in sourceSchema && sourceSchema.relationships
      ? sourceSchema.relationships
          .filter((relationship) => {
            return relationship.peer === peer;
          })
          .map((relationship) => {
            const relationshipData = objectDetailsData[relationship.name];
            return {
              value: relationshipData && "node" in relationshipData ? relationshipData.node : null,
              source: {
                type: "source",
                label: relationship.label ?? relationship.name,
                name: relationship.name,
              },
              isDefaultMatch: relationship.name === mapping.source_field_name,
            };
          })
      : [];

  const currentOption = availableOptions?.find((nodeOption) => {
    return nodeOption.source.name === fieldData?.source?.name;
  });

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <ComboboxTrigger>
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
                  field.onChange({
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
  objectDetailsData,
  sourceSchema,
  mapping,
  field,
  peer,
}: ConvertSourceRelationshipInputParams) => {
  const [open, setOpen] = useState(false);

  const fieldData = field.value;

  const availableOptions: Array<RelationshipManySourceOption> =
    "relationships" in sourceSchema && sourceSchema?.relationships
      ? sourceSchema.relationships
          ?.filter((relationship) => {
            // Get all relationships that use the same peer (can be cardinality one and many)
            return relationship.peer === peer && relationship.cardinality === "many";
          })
          .reduce((acc, relationship) => {
            const relationshipData = objectDetailsData[relationship.name];
            const objectsOptions =
              relationshipData &&
              "edges" in relationshipData &&
              Array.isArray(relationshipData.edges)
                ? relationshipData.edges.map((edge) => edge.node)
                : [];

            const option = {
              source: {
                type: "source",
                name: relationship.name,
                label: relationship.label,
              },
              value: objectsOptions,
              isDefaultMatch: relationship.name === mapping.source_field_name,
            };

            return [...acc, option];
          }, [])
      : [];

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
            "flex justify-between"
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
                  field.onChange({
                    source: {
                      type: "source",
                      label: option.source.label,
                      name: option.source.name,
                      node: option.value,
                    },
                    value: option.value?.map((node) => {
                      return node.id;
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

                    <Badge variant={"gray-outline"}>{option.source.label}</Badge>
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
