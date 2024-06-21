import { ElementRef, forwardRef, useState } from "react";
import { useAtomValue } from "jotai";
import { components } from "@/infraops";
import { store } from "@/state";
import { genericsState, IModelSchema, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { Select } from "@/components/inputs/select";
import { DynamicRelationshipFieldProps, FormFieldProps } from "@/components/form/type";
import { LabelFormField } from "@/components/form/fields/common";

export interface RelationshipFieldProps extends DynamicRelationshipFieldProps {}

// Select kind (select 2 steps) if needed
const RelationshipField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
  unique,
  ...props
}: RelationshipFieldProps) => {
  const { options, parent, relationship } = props;

  const generics = useAtomValue(genericsState);
  const schemaList = useAtomValue(schemaState);

  const [selectedKind, setSelectedKind] = useState(
    parent ? options?.find((option) => option.id === parent) : null
  );
  const [selectedParent, setSelectedParent] = useState(null);

  const generic = generics.find((generic) => generic.kind === relationship.peer);

  if (generic && relationship.cardinality === "one") {
    const nodes = store.get(schemaState);
    const profiles = store.get(profilesAtom);
    const schemaData = schemaList.find((schema) => schema.kind === selectedKind?.id);
    const parentRelationship = schemaData?.relationships?.find((rel) => rel.kind === "Parent");

    const genericOptions = (generic.used_by || []).map((name: string) => {
      const relatedSchema = [...nodes, ...profiles].find((s: any) => s.kind === name);

      if (relatedSchema) {
        return {
          id: name,
          name: relatedSchema.label || relatedSchema.name,
        };
      }
    });

    const kindOptions = Array.isArray(genericOptions)
      ? genericOptions.map((option) => ({
          name: option?.name,
          id: option?.id,
        }))
      : [];
    const selectedKindOption = kindOptions?.find((option) => option.id === selectedKind?.id);

    // Select the first option if the only available
    if (kindOptions?.length === 1 && !selectedKind) {
      setSelectedKind(kindOptions[0]);
    }

    // Select the kind after building the options from generics
    if (parent && !selectedKind && kindOptions?.length) {
      setSelectedKind(kindOptions?.find((option) => option.id === parent));
    }

    return (
      <div>
        <LabelFormField
          label={label}
          unique={unique}
          required={!!rules?.required}
          description={description}
        />

        <FormField
          key={`${name}_1`}
          name={name}
          rules={rules}
          defaultValue={defaultValue}
          render={({ field }) => {
            return (
              <div className="relative flex flex-col">
                <LabelFormField
                  label={"Kind"}
                  description="Kind of node to use as relationship"
                  unique={unique}
                  required={!!rules?.required}
                  variant="small"
                />

                <FormInput>
                  <RelationshipInput
                    {...field}
                    {...props}
                    options={kindOptions}
                    onChange={setSelectedKind}
                    value={selectedKind?.id}
                  />
                </FormInput>
                <FormMessage />
              </div>
            );
          }}
        />

        {selectedKind && (
          <FormField
            key={`${name}_parent`}
            name={name}
            rules={rules}
            defaultValue={defaultValue}
            render={({ field }) => {
              return (
                <div className="relative flex flex-col mt-1">
                  <LabelFormField
                    label={parentRelationship?.label ?? "Parent"}
                    description={parentRelationship?.description}
                    unique={unique}
                    required={!!rules?.required}
                    variant="small"
                  />

                  <FormInput>
                    <RelationshipInput
                      {...field}
                      {...props}
                      peer={parentRelationship?.peer}
                      disabled={props.disabled || !parentRelationship || !selectedKind?.id}
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

        {selectedKind && (
          <FormField
            key={`${name}_2`}
            name={name}
            rules={rules}
            defaultValue={defaultValue}
            render={({ field }) => {
              return (
                <div className="relative flex flex-col mt-1">
                  <LabelFormField
                    label={selectedKindOption?.name || "Node"}
                    unique={unique}
                    required={!!rules?.required}
                    description={description}
                    variant="small"
                  />

                  <FormInput>
                    <RelationshipInput
                      {...field}
                      {...props}
                      peer={selectedKind?.id}
                      parent={{ name: parentRelationship?.name, value: selectedParent?.id }}
                      disabled={props.disabled || !selectedKind?.id}
                      multiple={relationship.cardinality === "many"}
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
  }

  const schemaData = schemaList.find((schema) => schema.kind === relationship?.peer);
  const parentRelationship = schemaData?.relationships?.find((rel) => rel.kind === "Parent");

  return (
    <div>
      {parentRelationship && (
        <LabelFormField
          label={label}
          unique={unique}
          required={!!rules?.required}
          description={description}
        />
      )}

      {parentRelationship && (
        <FormField
          key={`${name}_parent`}
          name={name}
          rules={rules}
          defaultValue={defaultValue}
          render={({ field }) => {
            return (
              <div className="relative flex flex-col">
                <LabelFormField
                  label={parentRelationship?.label ?? "Parent"}
                  description="Parent to filter the available nodes"
                  unique={unique}
                  required={!!rules?.required}
                  variant="small"
                />

                <FormInput>
                  <RelationshipInput
                    {...field}
                    {...props}
                    peer={parentRelationship?.peer}
                    disabled={props.disabled}
                    onChange={setSelectedParent}
                    className="mt-1"
                  />
                </FormInput>
                <FormMessage />
              </div>
            );
          }}
        />
      )}

      <FormField
        key={name}
        name={name}
        rules={rules}
        defaultValue={defaultValue}
        render={({ field }) => {
          return (
            <div className="relative flex flex-col mt-1">
              {parentRelationship && (
                <LabelFormField
                  label={label}
                  unique={unique}
                  required={!!rules?.required}
                  description={description}
                  variant="small"
                />
              )}

              {!parentRelationship && (
                <LabelFormField
                  label={label}
                  unique={unique}
                  required={!!rules?.required}
                  description={description}
                />
              )}

              <FormInput>
                <RelationshipInput
                  {...field}
                  {...props}
                  parent={{ name: parentRelationship?.name, value: selectedParent?.id }}
                  multiple={relationship.cardinality === "many"}
                />
              </FormInput>
              <FormMessage />
            </div>
          );
        }}
      />
    </div>
  );
};

interface RelationshipInputProps extends FormFieldProps, RelationshipFieldProps {
  relationship: components["schemas"]["RelationshipSchema-Output"];
  schema: IModelSchema;
  onChange: (value: any) => void;
  value?: string;
  multiple?: boolean;
  className?: string;
}

// Select parent if needed
const RelationshipInput = forwardRef<ElementRef<typeof Select>, RelationshipInputProps>(
  ({ schema, value, options, relationship, ...props }, ref) => {
    return (
      <Select
        ref={ref}
        {...props}
        value={value}
        options={options ?? []}
        field={relationship}
        schema={schema}
        className="w-full"
      />
    );
  }
);

export default RelationshipField;
