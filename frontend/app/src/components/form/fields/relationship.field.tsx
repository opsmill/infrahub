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

  const [selectedLeft, setSelectedLeft] = useState(
    parent ? options?.find((option) => option.id === parent) : null
  );

  const generics = useAtomValue(genericsState);
  const generic = generics.find((generic) => generic.kind === relationship.peer);

  if (generic) {
    const nodes = store.get(schemaState);
    const profiles = store.get(profilesAtom);
    const options = (generic.used_by || []).map((name: string) => {
      const relatedSchema = [...nodes, ...profiles].find((s: any) => s.kind === name);

      if (relatedSchema) {
        return {
          id: name,
          name: relatedSchema.name,
        };
      }
    });

    const selectOptions = Array.isArray(options)
      ? options.map((o) => ({
          name: o.name,
          id: o.id,
        }))
      : [];

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
                  unique={unique}
                  required={!!rules?.required}
                  description={description}
                  variant="small"
                />

                <FormInput>
                  <RelationshipInput
                    {...field}
                    {...props}
                    options={selectOptions}
                    onChange={setSelectedLeft}
                    value={selectedLeft?.id}
                  />
                </FormInput>
                <FormMessage />
              </div>
            );
          }}
        />

        <FormField
          key={`${name}_2`}
          name={name}
          rules={rules}
          defaultValue={defaultValue}
          render={({ field }) => {
            return (
              <div className="relative flex flex-col mt-2">
                <LabelFormField
                  label={"Object"}
                  unique={unique}
                  required={!!rules?.required}
                  description={description}
                  variant="small"
                />

                <FormInput>
                  <RelationshipInput
                    {...field}
                    {...props}
                    peer={selectedLeft?.id}
                    disabled={props.disabled || !selectedLeft?.id}
                    className="mt-1"
                  />
                </FormInput>
                <FormMessage />
              </div>
            );
          }}
        />
      </div>
    );
  }

  return (
    <div>
      <FormField
        key={name}
        name={name}
        rules={rules}
        defaultValue={defaultValue}
        render={({ field }) => {
          return (
            <div className="relative flex flex-col">
              <LabelFormField
                label={label}
                unique={unique}
                required={!!rules?.required}
                description={description}
              />

              <FormInput>
                <RelationshipInput {...field} {...props} peer={relationship?.peer} />
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
        multiple={relationship.cardinality === "many"}
        className="w-full"
      />
    );
  }
);

export default RelationshipField;
