import { LabelFormField } from "@/components/form/fields/common";
import {
  DynamicRelationshipFieldProps,
  FormFieldProps,
  FormRelationshipValue,
} from "@/components/form/type";
import { updateRelationshipFieldValue } from "@/components/form/utils/updateFormFieldValue";
import { Select, SelectOption } from "@/components/inputs/select";
import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { getRelationshipParent } from "@/graphql/queries/objects/getRelationshipParent";
import useQuery from "@/hooks/useQuery";
import { components } from "@/infraops";
import { store } from "@/state";
import { IModelSchema, genericsState, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { ElementRef, forwardRef, useState } from "react";

const getGenericParentRelationship = (kind?: string) => {
  if (!kind) return;

  const nodes = store.get(schemaState);
  const schemaData = nodes.find((schema) => schema.kind === kind);
  return schemaData?.relationships?.find((rel) => rel.kind === "Parent");
};

const getParentRelationship = (peer?: string) => {
  if (!peer) return;

  const schemaList = useAtomValue(schemaState);
  const schemaData = schemaList.find((schema) => schema.kind === peer);
  return schemaData?.relationships?.find((rel) => rel.kind === "Parent");
};

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

  const isGeneric = generic && relationship.cardinality === "one";

  const parentRelationship = isGeneric
    ? getGenericParentRelationship(selectedKind?.id)
    : getParentRelationship(relationship?.peer);

  const kind = parentRelationship?.peer;
  const attribute = parentRelationship?.identifier?.split("__")[1];
  const id = Array.isArray(defaultValue?.value)
    ? defaultValue?.value?.map((v) => v.id)[0]
    : defaultValue?.value?.id;

  const queryString = getRelationshipParent({ kind, attribute: `${attribute}s__ids`, id });

  const query =
    kind && attribute && id
      ? gql`
          ${queryString}
        `
      : gql`
          query {
            ok
          }
        `;

  const { data } = useQuery(query, { skip: !parentRelationship?.kind || !id });

  const currentParent = data && kind && data[kind]?.edges[0]?.node;

  if (currentParent && !selectedParent) {
    setSelectedParent(currentParent);
  }

  if (isGeneric) {
    const profiles = store.get(profilesAtom);
    const genericOptions: SelectOption[] = (generic.used_by || [])
      .map((name: string) => {
        const relatedSchema = [...schemaList, ...profiles].find((s) => s.kind === name);

        if (relatedSchema) {
          return {
            id: name,
            name: relatedSchema.label || relatedSchema.name,
            badge: relatedSchema.namespace,
          };
        }
      })
      .filter((n) => !!n);

    const selectedKindOption = genericOptions?.find((option) => option.id === selectedKind?.id);

    // Select the first option if the only available
    if (genericOptions?.length === 1 && !selectedKind) {
      setSelectedKind(genericOptions[0]);
    }

    // Select the kind after building the options from generics
    if (parent && !selectedKind && genericOptions?.length) {
      setSelectedKind(genericOptions?.find((option) => option.id === parent));
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
          key={`${name}_1`}
          name={name}
          rules={rules}
          defaultValue={defaultValue}
          render={({ field }) => {
            return (
              <div className="relative flex flex-col space-y-1">
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
                    options={genericOptions}
                    onChange={setSelectedKind}
                    value={selectedKind?.id}
                  />
                </FormInput>
                <FormMessage />
              </div>
            );
          }}
        />

        {selectedKind && parentRelationship && (
          <FormField
            key={`${name}_parent`}
            name={name}
            rules={rules}
            defaultValue={defaultValue}
            render={({ field }) => {
              return (
                <div className="relative flex flex-col space-y-1">
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
                      value={currentParent?.id}
                      peer={parentRelationship?.peer}
                      disabled={props.disabled || !selectedKind?.id}
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
              const fieldData: FormRelationshipValue = field.value;

              return (
                <div className="relative flex flex-col space-y-1">
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
                      value={fieldData?.value}
                      onChange={(newValue) => {
                        field.onChange(updateRelationshipFieldValue(newValue, defaultValue));
                      }}
                      {...props}
                      options={[]}
                      peer={selectedKind?.id?.toString()}
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

  return (
    <div className="space-y-2">
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
            const fieldData = field.value;

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
                    value={fieldData?.value}
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
          const fieldData = field.value;

          return (
            <div className="relative flex flex-col space-y-2">
              <LabelFormField
                label={label}
                unique={unique}
                required={!!rules?.required}
                description={description}
                variant={parentRelationship && "small"}
                fieldData={fieldData}
              />

              <FormInput>
                <RelationshipInput
                  {...field}
                  value={fieldData?.value}
                  onChange={(newValue) => {
                    field.onChange(updateRelationshipFieldValue(newValue, defaultValue));
                  }}
                  {...props}
                  peer={relationship?.peer}
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
  value?: string | number;
  multiple?: boolean;
  className?: string;
}

// Select parent if needed
const RelationshipInput = forwardRef<ElementRef<typeof Select>, RelationshipInputProps>(
  ({ options, relationship, ...props }, ref) => {
    return (
      <Select
        ref={ref}
        {...props}
        options={options ?? []}
        field={relationship}
        className="w-full"
      />
    );
  }
);

export default RelationshipField;
