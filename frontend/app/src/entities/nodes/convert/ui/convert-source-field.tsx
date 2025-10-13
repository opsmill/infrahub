import { useAtomValue } from "jotai";

import { Col } from "@/shared/components/container";
import type { DynamicFieldProps } from "@/shared/components/form/type";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

import type { ConvertFieldMapping, ConvertFormFieldValue } from "@/entities/nodes/convert/types";
import { ConvertFieldLabel } from "@/entities/nodes/convert/ui/convert-field-label";
import { ConvertSourceAttributeInput } from "@/entities/nodes/convert/ui/convert-source-attribute-input";
import { ConvertSourceRelationshipManyInput } from "@/entities/nodes/convert/ui/convert-source-relationship-many-input";
import { ConvertSourceRelationshipOneInput } from "@/entities/nodes/convert/ui/convert-source-relationship-one-input";
import type { NodeObject } from "@/entities/nodes/types";
import { schemaKindNameState } from "@/entities/schema/stores/schemaKindName.atom";
import type { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";

interface ConvertSourceFieldProps extends Omit<DynamicFieldProps, "defaultValue"> {
  objectDetailsData: NodeObject;
  sourceSchema: ModelSchema;
  mapping?: ConvertFieldMapping;
  defaultValue: ConvertFormFieldValue;
  attribute?: AttributeSchema;
  relationship?: RelationshipSchema;
}

export function ConvertSourceField({
  objectDetailsData,
  sourceSchema,
  mapping,
  name,
  label,
  unique,
  description,
  rules,
  attribute,
  relationship,
  defaultValue,
}: ConvertSourceFieldProps) {
  const schemaKindLabel = useAtomValue(schemaKindNameState);

  return (
    <FormField
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      shouldUnregister={false}
      render={({ field }) => {
        return (
          <Col>
            <ConvertFieldLabel
              label={label}
              unique={unique}
              required={!!rules?.required}
              description={description}
              kind={attribute?.kind ?? schemaKindLabel[relationship?.peer ?? ""] ?? ""}
            />

            {attribute && (
              <FormInput>
                <ConvertSourceAttributeInput
                  sourceObject={objectDetailsData}
                  sourceSchema={sourceSchema}
                  mapping={mapping}
                  attribute={attribute}
                  value={field.value}
                  onChange={field.onChange}
                />
              </FormInput>
            )}

            {relationship?.peer && relationship.cardinality === "one" && (
              <FormInput>
                <ConvertSourceRelationshipOneInput
                  sourceObject={objectDetailsData}
                  sourceSchema={sourceSchema}
                  mapping={mapping}
                  peer={relationship.peer}
                  value={field.value}
                  onChange={field.onChange}
                />
              </FormInput>
            )}

            {relationship?.peer && relationship.cardinality === "many" && (
              <FormInput>
                <ConvertSourceRelationshipManyInput
                  sourceObject={objectDetailsData}
                  sourceSchema={sourceSchema}
                  mapping={mapping}
                  peer={relationship.peer}
                  value={field.value}
                  onChange={field.onChange}
                />
              </FormInput>
            )}

            <FormMessage />
          </Col>
        );
      }}
    />
  );
}
