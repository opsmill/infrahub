import { getRelationshipParent } from "@/entities/nodes/api/getRelationshipParent";
import { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";
import useQuery from "@/shared/api/graphql/useQuery";
import { LabelFormField } from "@/shared/components/form/fields/common";
import { PoolValue } from "@/shared/components/form/pool-selector";
import {
  DynamicRelationshipFieldProps,
  FormRelationshipValue,
} from "@/shared/components/form/type";
import { FormContext } from "@/shared/components/form/utils/form-context";
import { getPoolKindFromSchema } from "@/shared/components/form/utils/get-pool-kind-from-schema";
import { updateRelationshipFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { PoolSelect } from "@/shared/components/inputs/pool-select";
import { RelationshipInput } from "@/shared/components/inputs/relationship-one";

import { getParentRelationship } from "@/shared/components/form/utils/getParentRelationship";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";
import { gql } from "@apollo/client";
import { use, useState } from "react";
import { GenericRelationship } from "./generic-relationship.field";

export interface RelationshipFieldProps extends DynamicRelationshipFieldProps {
  parentDisabled?: boolean;
  defaultParent?: Node | null;
}

// Select kind (select 2 steps) if needed
const RelationshipField = (fieldProps: RelationshipFieldProps) => {
  const {
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
    ...props
  } = fieldProps;

  const formContext = use(FormContext);

  const [selectedParent, setSelectedParent] = useState<Node | null | undefined>(defaultParent);

  const { isGeneric: isPeerGeneric } = useSchema(relationship.peer);

  const parentRelationship = getParentRelationship(relationship?.peer);

  const { schema: parentRelationshipSchema } = useSchema(parentRelationship?.peer);

  const parentRelationshipAttribute = parentRelationshipSchema?.relationships?.find(
    (relationship) => {
      if (parentRelationship?.direction === "bidirectional") {
        return relationship.identifier === parentRelationship?.identifier;
      }

      if (parentRelationship?.direction === "inbound") {
        return (
          relationship.direction === "outbound" &&
          relationship.identifier === parentRelationship?.identifier
        );
      }

      if (parentRelationship?.direction === "outbound") {
        return (
          relationship.direction === "inbound" &&
          relationship.identifier === parentRelationship?.identifier
        );
      }

      return false;
    }
  );

  const id = defaultValue?.value?.id;

  const queryString = getRelationshipParent({
    kind: relationship?.peer,
    attribute: `${parentRelationshipAttribute?.name}__ids`,
    id,
  });

  const query =
    relationship?.peer && parentRelationshipAttribute?.name && id
      ? gql`
          ${queryString}
        `
      : gql`
          query {
            ok
          }
        `;

  const { data } = useQuery(query, { skip: !parentRelationshipSchema?.kind || !id });

  const currentParent = data && kind && data[kind]?.edges[0]?.node;

  if (currentParent && !selectedParent) {
    setSelectedParent(currentParent);
  }

  if (defaultParent && !selectedParent) {
    setSelectedParent(defaultParent);
  }

  if (isOfKind(parentRelationship?.peer, formContext.parentSchema) && !selectedParent) {
    setSelectedParent(formContext.parentData);
  }

  if (isPeerGeneric) {
    return <GenericRelationship {...fieldProps} />;
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
                    disabled={props.parentDisabled || props.disabled}
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
          const fieldData: FormRelationshipValue = field.value;

          const { peer } = relationship;
          const { schema: peerSchema } = useSchema(peer);
          const poolKind = peerSchema ? getPoolKindFromSchema(peerSchema) : null;
          const selectedPoolId = fieldData?.source?.type === "pool" ? fieldData.source.id : null;

          const onChange = (newValue: Node | PoolValue | null) => {
            field.onChange(updateRelationshipFieldValue(newValue, defaultValue));
          };

          const value =
            fieldData?.value && !Array.isArray(fieldData.value) ? (fieldData.value as Node) : null;

          return (
            <div className="relative flex flex-col space-y-2">
              <LabelFormField
                label={label}
                unique={unique}
                required={!!rules?.required}
                description={description}
                variant={parentRelationship ? "small" : undefined}
                fieldData={fieldData}
              />

              <div className="flex gap-2">
                <FormInput>
                  <RelationshipInput
                    {...field}
                    {...props}
                    value={value}
                    onChange={onChange}
                    peer={peer}
                    parent={{ name: parentRelationship?.name, value: selectedParent?.id }}
                  />
                </FormInput>

                {poolKind && peerSchema && (
                  <PoolSelect
                    poolKind={poolKind}
                    peerSchema={peerSchema}
                    selectedPoolId={selectedPoolId}
                    onChange={onChange}
                  />
                )}
              </div>
              <FormMessage />
            </div>
          );
        }}
      />
    </div>
  );
};

export default RelationshipField;
