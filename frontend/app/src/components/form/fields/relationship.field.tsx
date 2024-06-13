import { FormField, FormInput, FormLabel, FormMessage } from "@/components/ui/form";
import { Select } from "../../inputs/select";
import { ElementRef, forwardRef } from "react";
import { components } from "@/infraops";
import { genericsState, IModelSchema, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import { OpsSelect2Step } from "@/components/form/select-2-step";
import { store } from "@/state";
import { DynamicRelationshipFieldProps, FormFieldProps } from "@/components/form/type";
import { QuestionMark } from "@/components/display/question-mark";

export interface RelationshipFieldProps extends DynamicRelationshipFieldProps {}

const RelationshipField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
  ...props
}: RelationshipFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      render={({ field }) => {
        return (
          <div className="flex flex-col">
            <div className="px-1 mb-1 flex justify-between items-center gap-1">
              <FormLabel>
                {label} {rules?.required && "*"}
              </FormLabel>

              {description && <QuestionMark message={description} />}
            </div>

            <FormInput>
              <RelationshipInput {...field} {...props} />
            </FormInput>
            <FormMessage />
          </div>
        );
      }}
    />
  );
};

interface RelationshipInputProps extends FormFieldProps, RelationshipFieldProps {
  relationship: components["schemas"]["RelationshipSchema-Output"];
  schema: IModelSchema;
  onChange: (value: any) => void;
  value?: string;
}

const RelationshipInput = forwardRef<ElementRef<typeof Select>, RelationshipInputProps>(
  ({ schema, value, parent, relationship, ...props }, ref) => {
    if (relationship.cardinality === "many") {
      return (
        <Select
          ref={ref}
          {...props}
          multiple
          options={[]}
          peer={relationship.peer}
          field={relationship}
          schema={schema}
          className="w-full"
        />
      );
    }

    if (relationship.inherited) {
      const generics = store.get(genericsState);
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
          <OpsSelect2Step
            {...props}
            isOptional
            options={selectOptions}
            value={{
              parent: parent ?? null,
              child: value?.id ?? value ?? null,
            }}
            peer={relationship.peer}
            field={relationship}
            onChange={(newOption) => {
              props.onChange(newOption);
            }}
          />
        );
      }
    }

    return (
      <Select
        ref={ref}
        {...props}
        value={value}
        options={[]}
        peer={relationship.peer}
        field={relationship}
        schema={schema}
        className="w-full"
      />
    );
  }
);

export default RelationshipField;
