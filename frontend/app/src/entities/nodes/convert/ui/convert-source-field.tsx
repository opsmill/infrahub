import { useAtomValue } from "jotai";

import { Col } from "@/shared/components/container";
import type { FormFieldProps } from "@/shared/components/form/type";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

import type { ConvertFieldMapping } from "@/entities/nodes/convert/types";
import { ConvertFieldLabel } from "@/entities/nodes/convert/ui/convert-field-label";
import {
  ConvertSourceAttributeInput,
  ConvertSourceRelationshipManyInput,
  ConvertSourceRelationshipOneInput,
} from "@/entities/nodes/convert/ui/convert-source-input";
import type { NodeObject } from "@/entities/nodes/types";
import { schemaKindNameState } from "@/entities/schema/stores/schemaKindName.atom";
import type { ModelSchema } from "@/entities/schema/types";

interface ConvertSourceFieldProps extends FormFieldProps {
  objectDetailsData: NodeObject;
  sourceSchema: ModelSchema;
  mapping: ConvertFieldMapping;
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
              kind={attribute?.kind ?? schemaKindLabel[relationship?.peer]}
            />

            {attribute && (
              <FormInput>
                <ConvertSourceAttributeInput
                  objectDetailsData={objectDetailsData}
                  sourceSchema={sourceSchema}
                  mapping={mapping}
                  kind={attribute.kind}
                  field={field}
                />
              </FormInput>
            )}

            {relationship?.peer && relationship.cardinality === "one" && (
              <FormInput>
                <ConvertSourceRelationshipOneInput
                  objectDetailsData={objectDetailsData}
                  sourceSchema={sourceSchema}
                  mapping={mapping}
                  peer={relationship.peer}
                  field={field}
                />
              </FormInput>
            )}

            {relationship?.peer && relationship.cardinality === "many" && (
              <FormInput>
                <ConvertSourceRelationshipManyInput
                  objectDetailsData={objectDetailsData}
                  sourceSchema={sourceSchema}
                  mapping={mapping}
                  peer={relationship.peer}
                  field={field}
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
