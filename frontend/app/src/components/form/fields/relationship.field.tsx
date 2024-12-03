import { LabelFormField } from "@/components/form/fields/common";
import { DynamicRelationshipFieldProps } from "@/components/form/type";
import { updateRelationshipFieldValue } from "@/components/form/utils/updateFormFieldValue";
import { RelationshipInput } from "@/components/inputs/relationship-one";
import { Badge } from "@/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/components/ui/combobox";
import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { getRelationshipParent } from "@/graphql/queries/objects/getRelationshipParent";
import useQuery from "@/hooks/useQuery";
import { store } from "@/state";
import { genericsState, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import { Node } from "@/utils/getObjectItemDisplayValue";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { useState } from "react";

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
  type,
  options,
  parent,
  relationship,
  ...props
}: RelationshipFieldProps) => {
  const generics = useAtomValue(genericsState);
  const schemaList = useAtomValue(schemaState);

  const [selectedGeneric, setSelectedGeneric] = useState<Node | null>(
    parent ? options?.find((option) => option.id === parent) : null
  );
  const [selectedParent, setSelectedParent] = useState<Node | null>(null);

  const generic = generics.find((generic) => generic.kind === relationship.peer);

  const parentRelationship = generic
    ? getGenericParentRelationship(selectedGeneric?.id)
    : getParentRelationship(relationship?.peer);

  const kind = parentRelationship?.peer;
  const attribute = parentRelationship?.identifier?.split("__")[1];
  const id = defaultValue?.value?.id;

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

  if (generic) {
    const profiles = store.get(profilesAtom);
    const genericOptions = (generic.used_by || [])
      .map((name: string) => {
        const relatedSchema = [...schemaList, ...profiles].find((s) => s.kind === name);

        if (relatedSchema) {
          return {
            id: name,
            display_label: relatedSchema.label || relatedSchema.name,
            badge: relatedSchema.namespace,
          };
        }
      })
      .filter((n) => !!n);

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
            defaultValue={defaultValue}
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
                    value={selectedParent}
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
                  {...props}
                  value={fieldData?.value}
                  onChange={(newValue) => {
                    field.onChange(updateRelationshipFieldValue(newValue, defaultValue));
                  }}
                  peer={relationship?.peer}
                  parent={{ name: parentRelationship?.name, value: selectedParent?.id }}
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

export default RelationshipField;
