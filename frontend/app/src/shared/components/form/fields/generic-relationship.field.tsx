import { NodeObject } from "@/entities/nodes/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { FormContext } from "@/shared/components/form/utils/form-context";
import { getParentRelationship } from "@/shared/components/form/utils/getParentRelationship";
import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import { use, useState } from "react";
import { RelationshipInput } from "../../inputs/relationship-one";
import { FormField, FormInput, FormMessage } from "../../ui/form";
import { DynamicRelationshipFieldProps } from "../type";
import { updateRelationshipFieldValue } from "../utils/updateFormFieldValue";
import { LabelFormField } from "./common";

export interface GenericRelationshipFieldProps extends DynamicRelationshipFieldProps {
  parentDisabled?: boolean;
  defaultParent?: Node | null;
  kind: string;
}

export const GenericRelationship = ({
  defaultValue,
  defaultParent,
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
  kind,
  ...props
}: GenericRelationshipFieldProps) => {
  const formContext = use(FormContext);

  const { schema: peerSchema } = useSchema(kind);

  const [selectedGeneric, setSelectedGeneric] = useState<NodeObject | null>(
    parent ? options?.find((option) => option.id === parent) : null
  );
  const [selectedParent, setSelectedParent] = useState<Node | null | undefined>(defaultParent);

  const genericOptions = (peerSchema.used_by || [])
    .map((name: string) => {
      const { schema: relatedSchema } = useSchema(name);

      if (relatedSchema) {
        return {
          id: name,
          display_label: relatedSchema.label || relatedSchema.name,
          badge: relatedSchema.namespace,
        };
      }
    })
    .filter((n) => !!n);

  const parentRelationship = getParentRelationship(selectedGeneric?.id);

  // Select the first option if the only available
  if (genericOptions?.length === 1 && !selectedGeneric) {
    setSelectedGeneric(genericOptions[0]);
  }

  // Select the kind after building the options from generics
  if (parent && !selectedGeneric && genericOptions?.length) {
    setSelectedGeneric(genericOptions?.find((option) => option.id === parent));
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
        render={() => {
          const [open, setOpen] = useState(false);

          return (
            <div className="relative flex flex-col space-y-1">
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
                      <div className="w-full flex justify-between" data-testid="select-value">
                        {selectedGeneric.display_label} <Badge>{selectedGeneric.badge}</Badge>
                      </div>
                    )}
                  </ComboboxTrigger>
                </FormInput>

                <ComboboxContent>
                  <ComboboxList>
                    <ComboboxEmpty>No schema found.</ComboboxEmpty>
                    {genericOptions.map((item) => {
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

      {selectedGeneric && parentRelationship && (
        <FormField
          key={`${name}_parent`}
          name={`${name}_parent`}
          defaultValue={defaultValue}
          render={({ field }) => {
            return (
              <div className="relative flex flex-col space-y-1">
                <LabelFormField
                  label={parentRelationship?.label ?? "Parent"}
                  description={parentRelationship?.description}
                  unique={unique}
                  variant="small"
                />

                <FormInput>
                  <RelationshipInput
                    {...field}
                    value={selectedParent}
                    peer={parentRelationship.peer}
                    disabled={props.disabled || !selectedGeneric?.id}
                    onChange={setSelectedParent}
                    className="mt-2"
                  />
                </FormInput>
                <FormMessage />
              </div>
            );
          }}
        />
      )}
      {selectedGeneric && (
        <FormField
          key={name}
          name={name}
          rules={rules}
          render={({ field }) => {
            const fieldData = field.value;

            return (
              <div className="relative flex flex-col space-y-1">
                <LabelFormField
                  label={selectedGeneric?.display_label || "Node"}
                  unique={unique}
                  required={!!rules?.required}
                  description={description}
                  variant="small"
                />
                <FormInput>
                  <RelationshipInput
                    {...field}
                    {...props}
                    options={undefined}
                    value={fieldData?.value}
                    onChange={(newValue) => {
                      field.onChange(updateRelationshipFieldValue(newValue, defaultValue));
                    }}
                    peer={selectedGeneric?.id}
                    parent={{ name: parentRelationship?.name, value: selectedParent?.id }}
                    disabled={props.disabled || !selectedGeneric?.id}
                    className="mt-2"
                  />
                </FormInput>
                <FormMessage />
              </div>
            );
          }}
        />
      )}
    </div>
  );
};
