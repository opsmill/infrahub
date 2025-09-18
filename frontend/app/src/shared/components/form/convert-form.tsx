import { useAtomValue } from "jotai";
import React from "react";

import { Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { ConvertLabelFormField } from "@/shared/components/form/fields/common";
import { FormAttributeValue } from "@/shared/components/form/type";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import {
  ConvertSourceAttributeInput,
  ConvertSourceRelationshipOneInput,
} from "@/shared/components/inputs/convert-source-input";
import { Input } from "@/shared/components/inputs/input";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Form, FormField, FormInput, FormMessage, FormSubmit } from "@/shared/components/ui/form";

import { useFieldsMappingTypeConversion } from "@/entities/nodes/object/domain/get-convert-fields-mappings.query";
import { NodeObject } from "@/entities/nodes/types";
import { schemaKindNameState } from "@/entities/schema/stores/schemaKindName.atom";
import { ModelSchema } from "@/entities/schema/types";

export type ConvertFormProps = {
  objectDetailsData: NodeObject;
  sourceSchema: ModelSchema;
  targetSchema: ModelSchema;
};

const ConvertForm = ({ objectDetailsData, sourceSchema, targetSchema }: ConvertFormProps) => {
  const scheaKindLabel = useAtomValue(schemaKindNameState);
  const {
    data: mappings,
    isPending,
    error,
  } = useFieldsMappingTypeConversion({
    sourceKind: sourceSchema.kind,
    targetKind: targetSchema.kind,
  });

  const fields = getFormFieldsFromSchema({ schema: targetSchema });
  const fieldsWithMappings = fields.map((field) => {
    return {
      ...field,
      defaultValue: {
        source: {
          type: "convert",
          fieldLabel: field.label,
        },
        value: objectDetailsData[field.name]?.value,
      },
    };
  });

  if (isPending) {
    return <LoadingIndicator />;
  }

  if (error) {
    return <ErrorScreen message="An error occurred while fetching the fields mapping" />;
  }

  const formMappingDefaultValues = fieldsWithMappings.reduce((acc, field) => {
    return { ...acc, [field.name]: field.defaultValue };
  }, {});

  const handleSubmit = (data) => {
    console.log("data: ", data);
  };

  return (
    <Form defaultValues={formMappingDefaultValues} onSubmit={handleSubmit}>
      {fieldsWithMappings.map((fieldSchema) => {
        const { name, label, unique, description, defaultValue, rules } = fieldSchema;

        return (
          <FormField
            key={name}
            name={name}
            rules={rules}
            defaultValue={defaultValue}
            render={({ field }) => {
              const [sourceSelection, setSourceSelection] = React.useState(
                defaultValue?.source?.type === "convert" ? "source" : "custom"
              );

              const fieldData: FormAttributeValue = field.value;

              const handleSourceChange = (newSource: string) => {
                setSourceSelection(newSource);

                if (newSource === "source") {
                  field.onChange({
                    source: { type: "source", fieldLabel: label },
                    value: defaultValue.value,
                  });
                }

                if (newSource === "custom") {
                  field.onChange(updateFormFieldValue(defaultValue.value, defaultValue));
                }
              };

              const handleSourceValueChange = (option) => {
                field.onChange({
                  source: { type: "source", fieldLabel: label },
                  value: option.value,
                });
              };

              return (
                <div className="space-y-2">
                  <ConvertLabelFormField
                    label={label}
                    unique={unique}
                    required={!!rules?.required}
                    description={description}
                    kind={
                      fieldSchema.attribute?.kind ?? scheaKindLabel[fieldSchema.relationship?.peer]
                    }
                    onChange={handleSourceChange}
                    value={sourceSelection}
                  />

                  <Row>
                    <FormInput>
                      <>
                        {sourceSelection === "source" && fieldSchema.attribute && (
                          <ConvertSourceAttributeInput
                            objectDetailsData={objectDetailsData}
                            sourceSchema={sourceSchema}
                            mapping={mappings?.[field.name]}
                            onSelect={handleSourceValueChange}
                            kind={fieldSchema.attribute.kind}
                            fieldData={fieldData}
                          />
                        )}

                        {sourceSelection === "source" &&
                          fieldSchema.relationship?.peer &&
                          fieldSchema.relationship.cardinality === "one" && (
                            <ConvertSourceRelationshipOneInput
                              objectDetailsData={objectDetailsData}
                              sourceSchema={sourceSchema}
                              mapping={mappings?.[field.name]}
                              onSelect={handleSourceValueChange}
                              peer={fieldSchema.relationship.peer}
                              fieldData={fieldData}
                            />
                          )}

                        {sourceSelection !== "source" && (
                          <Input
                            {...field}
                            value={(fieldData?.value as string) ?? ""}
                            onChange={(newValue: string) => {
                              field.onChange(updateFormFieldValue(newValue, defaultValue));
                            }}
                          />
                        )}
                      </>
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
