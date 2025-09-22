import { useAtomValue } from "jotai";
import React from "react";

import { Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { ConvertLabelFormField } from "@/shared/components/form/fields/common";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import {
  ConvertSourceAttributeInput,
  ConvertSourceRelationshipManyInput,
  ConvertSourceRelationshipOneInput,
} from "@/shared/components/inputs/convert-source-input";
import { Input } from "@/shared/components/inputs/input";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Form, FormField, FormInput, FormMessage, FormSubmit } from "@/shared/components/ui/form";

import { useGetObjectConvertFieldsMapping } from "@/entities/nodes/object/domain/get-object-convert-fields-mapping.query";
import type { NodeObject } from "@/entities/nodes/types";
import { schemaKindNameState } from "@/entities/schema/stores/schemaKindName.atom";
import type { ModelSchema } from "@/entities/schema/types";

export type ConvertFormProps = {
  objectDetailsData: NodeObject;
  sourceSchema: ModelSchema;
  targetSchema: ModelSchema;
};

const ConvertForm = ({ objectDetailsData, sourceSchema, targetSchema }: ConvertFormProps) => {
  const schemaKindLabel = useAtomValue(schemaKindNameState);
  const {
    data: mappings,
    isPending,
    error,
  } = useGetObjectConvertFieldsMapping({
    sourceKind: sourceSchema.kind!,
    targetKind: targetSchema.kind!,
  });

  const fields = getFormFieldsFromSchema({
    schema: targetSchema,
    parentSchema: null,
    parentData: null,
  });

  if (isPending) {
    return <LoadingIndicator />;
  }

  if (error) {
    return <ErrorScreen message="An error occurred while fetching the fields mapping" />;
  }

  const formDefaultValues = fields.reduce((acc, field) => {
    return { ...acc, [field.name]: field.defaultValue };
  }, {});

  const formMappingsDefaultValues = fields.reduce((acc, field) => {
    return {
      ...acc,
      [field.name]: {
        source: {
          type: "convert",
          fieldLabel: field.label,
        },
        value: objectDetailsData[field.name]?.value,
      },
    };
  });

  const handleSubmit = (data) => {
    console.log("data: ", data);
  };

  return (
    <Form onSubmit={handleSubmit}>
      {fields.map(({ name, label, unique, description, rules, attribute, relationship }) => {
        return (
          <FormField
            key={name}
            name={name}
            rules={rules}
            render={({ field }) => {
              const hasMapping = !!mappings[name]?.source_field_name;

              const initialSource = hasMapping ? "source" : "custom";
              const [sourceSelection, setSourceSelection] = React.useState(initialSource);

              const defaultValue =
                hasMapping && sourceSelection === "source"
                  ? formMappingsDefaultValues[name]
                  : formDefaultValues[name];

              const fieldData: FormAttributeValue = field.value ?? defaultValue;

              const handleSourceChange = (newSource: string) => {
                setSourceSelection(newSource);

                if (newSource === "source") {
                  field.onChange({
                    source: { type: "source", fieldLabel: label },
                    value: formMappingsDefaultValues[name]?.value,
                  });
                }

                if (newSource === "custom") {
                  field.onChange({
                    source: { type: "schema" },
                    value: formDefaultValues[name]?.value,
                  });
                }
              };

              const handleSourceValueChange = (newOption) => {
                field.onChange({
                  source: { type: "source", fieldLabel: label },
                  value: newOption.value,
                });
              };

              const handleInputValueChange = (newValue: string) => {
                field.onChange({
                  source: { type: "user" },
                  value: newValue,
                });
              };

              return (
                <div className="space-y-2">
                  <ConvertLabelFormField
                    label={label}
                    unique={unique}
                    required={!!rules?.required}
                    description={description}
                    kind={attribute?.kind ?? schemaKindLabel[relationship?.peer]}
                    onChange={handleSourceChange}
                    value={sourceSelection}
                  />

                  <Row>
                    <FormInput>
                      <div className="grow">
                        {sourceSelection === "source" && attribute && (
                          <ConvertSourceAttributeInput
                            objectDetailsData={objectDetailsData}
                            sourceSchema={sourceSchema}
                            mapping={mappings?.[field.name]}
                            onSelect={handleSourceValueChange}
                            kind={attribute.kind}
                            fieldData={fieldData}
                          />
                        )}

                        {sourceSelection === "source" &&
                          relationship?.peer &&
                          relationship.cardinality === "one" && (
                            <ConvertSourceRelationshipOneInput
                              objectDetailsData={objectDetailsData}
                              sourceSchema={sourceSchema}
                              mapping={mappings?.[field.name]}
                              onSelect={handleSourceValueChange}
                              peer={relationship.peer}
                              fieldData={fieldData}
                            />
                          )}

                        {sourceSelection === "source" &&
                          relationship?.peer &&
                          relationship.cardinality === "many" && (
                            <ConvertSourceRelationshipManyInput
                              objectDetailsData={objectDetailsData}
                              sourceSchema={sourceSchema}
                              mapping={mappings?.[field.name]}
                              onSelect={handleSourceValueChange}
                              peer={relationship.peer}
                              fieldData={fieldData}
                            />
                          )}

                        {sourceSelection !== "source" && (
                          <Input
                            {...field}
                            value={fieldData?.value ?? ""}
                            onChange={handleInputValueChange}
                          />
                        )}
                      </div>
                    </FormInput>
                  </Row>

                  <FormMessage />
                </div>
              );
            }}
          />
        );
      })}

      <div className="text-right">
        <FormSubmit>Convert</FormSubmit>
      </div>
    </Form>
  );
};

export default ConvertForm;
