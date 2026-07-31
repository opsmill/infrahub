import { useId, useRef, useState } from "react";
import { useFormContext } from "react-hook-form";

import { Col } from "@/shared/components/container";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
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
import { useDefaultParent } from "@/entities/nodes/relationships/ui/queries/get-default-parent.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import { useCommonParentFilter } from "./useCommonParentFilter";

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
  shouldUnregister,
  ...props
}: GenericRelationshipFieldProps) => {
  const { schema: peerSchema, isGeneric } = useSchema(relationship?.peer);

  const defaultSelectedGeneric = parent ? options?.find((option) => option.id === parent) : null;

  const [selectedGeneric, setSelectedGeneric] = useState<GenericOption | null>(
    defaultSelectedGeneric as GenericOption | null
  );

  const parentRelationship = selectedGeneric?.id && getParentRelationship(selectedGeneric.id);
  const commonParent = useCommonParentFilter(relationship, name);
  // When common_parent drives the filter from a sibling field, the manual "Parent" picker
  // is redundant — hide it and source the peer filter from the sibling value instead.
  const showManualParent = !commonParent.isActive && !!parentRelationship;

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
  const hasDerivedKindFromDefault = useRef(false);

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

  // A default value (e.g. a parent pre-filled from the object being viewed) carries
  // its concrete node kind. Derive the selected kind from it once, so the value is shown
  // even when the generic is implemented by more than one node and cannot auto-select —
  // without re-selecting after the user has explicitly cleared the kind.
  const defaultValueKind =
    defaultValue?.value && !Array.isArray(defaultValue.value)
      ? (defaultValue.value as Node).__typename
      : undefined;
  if (
    defaultValueKind &&
    !selectedGeneric &&
    !hasDerivedKindFromDefault.current &&
    genericOptions?.length
  ) {
    const foundOption = genericOptions.find((option) => option.id === defaultValueKind);
    if (foundOption) {
      hasDerivedKindFromDefault.current = true;
      setSelectedGeneric(foundOption);
    }
  }

  if (!selectedParent && defaultParent) {
    setSelectedParent(defaultParent);
  }

  const form = useFormContext();

  // A user switching the kind invalidates any node picked under the previous kind, along with
  // the parent used to filter it, so clear both. Only wired to the picker, not the automatic
  // derivation above, so a pre-filled value is preserved on mount. Validation is not forced
  // here — flagging the field required before the user can pick a node under the new kind
  // would be premature.
  const handleKindChange = (value: GenericOption | null) => {
    setSelectedGeneric(value);
    setSelectedParent(null);
    form.setValue(name, DEFAULT_FORM_FIELD_VALUE, { shouldDirty: true });
  };

  return (
    <div className="space-y-2">
      <LabelFormField
        label={label}
        unique={unique}
        required={!!rules?.required}
        description={description}
      />

      <GenericSchemaPicker
        genericOptions={genericOptions}
        selectedGeneric={selectedGeneric}
        setSelectedGeneric={handleKindChange}
      />

      {showManualParent && parentRelationship && (
        <Col>
          <LabelFormField
            label={parentRelationship?.label ?? "Parent"}
            description={parentRelationship?.description}
            unique={unique}
            variant="small"
          />
          <RelationshipInput
            name={name + "_parent"}
            value={selectedParent ?? null}
            peer={parentRelationship.peer}
            disabled={props.disabled || !selectedGeneric?.id}
            onChange={(value) => setSelectedParent(value as Node | null)}
          />
        </Col>
      )}

      <FormField
        key={name}
        name={name}
        rules={rules}
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
                    parent={
                      commonParent.isActive
                        ? commonParent.parent
                        : { name: parentRelationship?.name, value: selectedParent?.id }
                    }
                    addNewInitialObject={commonParent.addNewInitialObject}
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

const GenericSchemaPicker = ({
  genericOptions,
  selectedGeneric,
  setSelectedGeneric,
}: {
  genericOptions: GenericOption[];
  selectedGeneric: GenericOption | null;
  setSelectedGeneric: (value: GenericOption | null) => void;
}) => {
  const id = useId();
  const [open, setOpen] = useState(false);

  return (
    <Col>
      <LabelFormField
        label="Kind"
        description="Kind of node to use as relationship"
        variant="small"
        htmlFor={id}
      />

      <Combobox open={open} onOpenChange={setOpen}>
        <ComboboxTrigger id={id}>
          {selectedGeneric && (
            <div className="flex w-full justify-between" data-testid="select-value">
              {selectedGeneric.display_label} <Badge>{selectedGeneric.badge}</Badge>
            </div>
          )}
        </ComboboxTrigger>

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
    </Col>
  );
};
