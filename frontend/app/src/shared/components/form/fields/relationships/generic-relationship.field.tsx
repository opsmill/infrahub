import { useState } from "react";

import { LabelFormField } from "@/shared/components/form/fields/common";
import type { DynamicRelationshipFieldProps } from "@/shared/components/form/type";
import { getParentRelationship } from "@/shared/components/form/utils/getParentRelationship";
import { updateRelationshipFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { RelationshipInput } from "@/shared/components/inputs/relationship-one";
import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";
import { Input } from "@/shared/components/ui/input";

import type { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import { useDefaultParent } from "@/entities/nodes/relationships/domain/get-default-parent.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface GenericOption extends Node {
  id: string;
  display_label: string;
  badge: string;
}

export interface GenericRelationshipFieldProps extends DynamicRelationshipFieldProps {
  parentDisabled?: boolean;
}

export const GenericRelationshipField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
  unique,
  type,
  options,
  parent,
  relationship,
  schema,
  shouldUnregister,
  ...props
}: GenericRelationshipFieldProps) => {
  const { schema: peerSchema, isGeneric } = useSchema(relationship?.peer);

  const defaultSelectedGeneric = parent ? options?.find((option) => option.id === parent) : null;

  const [selectedGeneric, setSelectedGeneric] = useState<GenericOption | null>(
    defaultSelectedGeneric as GenericOption | null
  );

  const parentRelationship = selectedGeneric?.id && getParentRelationship(selectedGeneric.id);

  const { data: defaultParent } = useDefaultParent({
    defaultValue,
    parentRelationship: parentRelationship
      ? {
          peer: parentRelationship.peer,
          direction: parentRelationship.direction,
          identifier: parentRelationship.identifier ?? undefined,
        }
      : undefined,
  });

  const [selectedParent, setSelectedParent] = useState<Node | null>(defaultParent || null);

  const genericOptions = (isGeneric ? (peerSchema?.used_by ?? []) : [])
    .map((name: string) => {
      const { schema: relatedSchema } = useSchema(name);

      if (relatedSchema) {
        return {
          id: name,
          display_label: relatedSchema.label || relatedSchema.name,
          badge: relatedSchema.namespace,
        };
      }

      return null;
    })
    .filter((n): n is GenericOption => n !== null);

  // Select the first option if the only available
  if (genericOptions?.length === 1 && !selectedGeneric) {
    setSelectedGeneric(genericOptions[0] ?? null);
  }

  // Select the kind after building the options from generics
  if (parent && !selectedGeneric && genericOptions?.length) {
    const foundOption: GenericOption | undefined = genericOptions.find(
      (option: GenericOption) => option.id === parent
    );
    if (foundOption) {
      setSelectedGeneric(foundOption);
    }
  }

  if (!selectedParent && defaultParent) {
    setSelectedParent(defaultParent);
  }

  return (
    <div className="space-y-2">
      <LabelFormField
        label={label}
        unique={unique}
        required={!!rules?.required}
        description={description}
      />

      <FormField
        key={`${name}_generic`}
        name={`${name}_generic`}
        defaultValue={defaultValue}
        shouldUnregister={shouldUnregister}
        render={() => {
          const [open, setOpen] = useState(false);

          return (
            <div className="relative flex flex-col space-y-2">
              <LabelFormField
                label={"Kind"}
                description="Kind of node to use as relationship"
                unique={unique}
                variant="small"
              />

              <Combobox open={open} onOpenChange={setOpen}>
                <FormInput>
                  <ComboboxTrigger>
                    {selectedGeneric && (
                      <div className="flex w-full justify-between" data-testid="select-value">
                        {selectedGeneric.display_label} <Badge>{selectedGeneric.badge}</Badge>
                      </div>
                    )}
                  </ComboboxTrigger>
                </FormInput>

                <ComboboxContent>
                  <ComboboxList>
                    <ComboboxEmpty>No schema found.</ComboboxEmpty>
                    {genericOptions.map((item: GenericOption) => {
                      return (
                        <ComboboxItem
                          key={item.id}
                          value={item.id}
                          selectedValue={selectedGeneric?.id}
                          onSelect={() => {
                            setSelectedGeneric(item.id === selectedGeneric?.id ? null : item);
                            setOpen(false);
                          }}
                        >
                          {item.display_label}
                          <Badge className="ml-auto">{item.badge}</Badge>
                        </ComboboxItem>
                      );
                    })}
                  </ComboboxList>
                </ComboboxContent>
              </Combobox>

              <FormMessage />
            </div>
          );
        }}
      />

      {parentRelationship && (
        <FormField
          key={`${name}_parent`}
          name={`${name}_parent`}
          defaultValue={defaultValue}
          shouldUnregister={shouldUnregister}
          render={({ field }) => {
            return (
              <div className="relative flex flex-col space-y-2">
                <LabelFormField
                  label={parentRelationship?.label ?? "Parent"}
                  description={parentRelationship?.description}
                  unique={unique}
                  variant="small"
                />
                <div>
                  <FormInput>
                    <RelationshipInput
                      {...field}
                      value={selectedParent ?? null}
                      peer={parentRelationship.peer}
                      disabled={props.disabled || !selectedGeneric?.id}
                      onChange={(value) => setSelectedParent(value as Node | null)}
                      className="mt-2"
                    />
                  </FormInput>
                  <FormMessage />
                </div>
              </div>
            );
          }}
        />
      )}

      <FormField
        key={name}
        name={name}
        rules={rules}
        disabled={!selectedGeneric?.id}
        shouldUnregister={shouldUnregister}
        render={({ field }) => {
          const fieldData = field.value;

          if (!selectedGeneric?.id) {
            return (
              <div className="relative flex flex-col space-y-2">
                <LabelFormField
                  label={selectedGeneric?.display_label ?? "Select a kind first"}
                  unique={unique}
                  required={!!rules?.required}
                  description={description}
                  variant="small"
                  className="italic"
                />
                <FormInput>
                  <Input disabled name="node-placholder" />
                </FormInput>
              </div>
            );
          }

          return (
            <div className="relative flex flex-col space-y-2">
              <LabelFormField
                label={selectedGeneric?.display_label ?? "Node"}
                unique={unique}
                required={!!rules?.required}
                description={description}
                variant="small"
              />
              <div>
                <FormInput>
                  <RelationshipInput
                    {...field}
                    {...props}
                    options={undefined}
                    value={fieldData?.value}
                    onChange={(newValue) => {
                      field.onChange(updateRelationshipFieldValue(newValue, defaultValue));
                    }}
                    peer={selectedGeneric?.id ?? ""}
                    parent={{ name: parentRelationship?.name, value: selectedParent?.id }}
                    disabled={props.disabled || !selectedGeneric?.id}
                  />
                </FormInput>
                <FormMessage />
              </div>
            </div>
          );
        }}
      />
    </div>
  );
};
