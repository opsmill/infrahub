import { useAtomValue } from "jotai";
import { useNavigate } from "react-router";
import { toast } from "react-toastify";

import { constructPath } from "@/shared/api/rest/fetch";
import { Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { ConvertLabelFormField } from "@/shared/components/form/fields/common";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import {
  ConvertSourceAttributeInput,
  ConvertSourceRelationshipManyInput,
  ConvertSourceRelationshipOneInput,
} from "@/shared/components/inputs/convert-source-input";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Form, FormField, FormInput, FormMessage, FormSubmit } from "@/shared/components/ui/form";

import { useConvertObjectMutation } from "@/entities/nodes/object/domain/convert-object.mutation";
import { useGetObjectConvertFieldsMapping } from "@/entities/nodes/object/domain/get-object-convert-fields-mapping.query";
import type { NodeObject } from "@/entities/nodes/types";
import { schemaKindNameState } from "@/entities/schema/stores/schemaKindName.atom";
import type { ModelSchema } from "@/entities/schema/types";

import { Radio, RadioGroup } from "../aria/radio-group";
import { ALERT_TYPES, Alert } from "../ui/alert";
import { DynamicField } from "./dynamic-form";

export type ConvertFormProps = {
  objectDetailsData: NodeObject;
  sourceSchema: ModelSchema;
  targetSchema: ModelSchema;
};

const ConvertFormWapper = ({ objectDetailsData, sourceSchema, targetSchema }: ConvertFormProps) => {
  const {
    data: mappings,
    isPending,
    error,
  } = useGetObjectConvertFieldsMapping({
    sourceKind: sourceSchema.kind!,
    targetKind: targetSchema.kind!,
  });

  if (isPending) {
    return <LoadingIndicator />;
  }

  if (error) {
    return <ErrorScreen message="An error occurred while fetching the fields mapping" />;
  }

  return (
    <ConvertForm
      mappings={mappings}
      objectDetailsData={objectDetailsData}
      sourceSchema={sourceSchema}
      targetSchema={targetSchema}
    />
  );
};

const ConvertForm = ({
  mappings,
  objectDetailsData,
  sourceSchema,
  targetSchema,
}: ConvertFormProps) => {
  const navigate = useNavigate();

  const { mutateAsync: convertObject } = useConvertObjectMutation();

  const fields = getFormFieldsFromSchema({
    schema: targetSchema,
    parentSchema: null,
    parentData: null,
  });

  const formDefaultValues = fields.reduce((acc, field) => {
    const hasMapping = !!mappings[field.name]?.source_field_name;

    if (!hasMapping) {
      return { ...acc, [field.name]: field.defaultValue };
    }

    // Relationship many
    if (objectDetailsData[field.name]?.edges) {
      const nodes = objectDetailsData[field.name]?.edges?.map((edge) => {
        return edge.node;
      });

      return {
        ...acc,
        [field.name]: {
          source: {
            type: "source",
            label: field.label,
            name: field.name,
            values: nodes.reduce((acc, node) => {
              return {
                ...acc,
                [node.id]: {
                  label: field.label,
                  name: field.name,
                },
              };
            }, {}),
          },
          value: nodes.map((node) => {
            return node.id;
          }),
        },
      };
    }

    // Relationship one
    if (objectDetailsData[field.name]?.node) {
      return {
        ...acc,
        [field.name]: {
          source: {
            type: "source",
            label: field.label,
            name: field.name,
          },
          value: objectDetailsData[field.name]?.node?.id,
        },
      };
    }

    // Attribute
    return {
      ...acc,
      [field.name]: {
        source: {
          type: "source",
          label: field.label,
          name: field.name,
        },
        value: objectDetailsData[field.name]?.value,
      },
    };
  }, {});

  const handleSubmit = async (formData) => {
    const fieldsMapping = Object.entries(formData).reduce((acc, [fieldName, fieldData]) => {
      if (fieldData.source?.type === "source") {
        return {
          ...acc,
          [fieldName]: {
            source_field: fieldData.source.name,
          },
        };
      }

      if (fieldData.source?.type === "schema") {
        return {
          ...acc,
          [fieldName]: {
            data: { use_default_value: true },
          },
        };
      }

      if (Array.isArray(fieldData.value)) {
        return {
          ...acc,
          [fieldName]: {
            data: { peer_ids: fieldData.value },
          },
        };
      }

      if (fieldData.source?.node) {
        return {
          ...acc,
          [fieldName]: {
            data: { peer_id: fieldData.value },
          },
        };
      }

      if (fieldData.value) {
        return {
          ...acc,
          [fieldName]: {
            data: { attribute_value: fieldData.value },
          },
        };
      }

      return acc;
    }, {});

    await convertObject(
      { nodeId: objectDetailsData.id, targetKind: targetSchema.kind, fieldsMapping },
      {
        onSuccess: async (result) => {
          toast(<Alert type={ALERT_TYPES.SUCCESS} message="Object converted!" />);
          const path = constructPath(`/objects/${targetSchema.kind}/${result.id}`);

          navigate(path);
        },
        onError: (error) => {
          console.error("Error when logging in: ", error);
          toast(
            <Alert
              type={ALERT_TYPES.ERROR}
              message="An error occurred while converting the object"
            />
          );
        },
      }
    );
  };

  return (
    <Form onSubmit={handleSubmit}>
      <div className="divide-y divide-gray-300">
        {fields.map(({ ...fieldProps }) => {
          console.log("fieldProps: ", fieldProps);
          const {
            name,
            label,
            type,
            unique,
            description,
            rules,
            attribute,
            relationship,
            defaultValue: fieldDefaultValue,
          } = fieldProps;

          const hasMapping = !!mappings[name]?.source_field_name;
          console.log("hasMapping: ", hasMapping);

          const schemaKindLabel = useAtomValue(schemaKindNameState);

          const defaultValue = formDefaultValues[name];

          return (
            <FormField
              key={name}
              name={name}
              rules={rules}
              defaultValue={defaultValue}
              render={({ field }) => {
                const fieldData = field.value;
                console.log("---");
                console.log("fieldData: ", name, fieldData);
                console.log("fieldDefaultValue?.source: ", fieldDefaultValue?.source);
                console.log(
                  'fieldData?.source?.type === "source": ',
                  fieldData?.source?.type === "source"
                );

                const sourceDefaultValue = {
                  source: { ...defaultValue?.source, type: "source" },
                  value: defaultValue?.value,
                };
                console.log("sourceDefaultValue: ", sourceDefaultValue);

                const handleSourceChange = (newSource: string) => {
                  if (newSource === "source") {
                    field.onChange(sourceDefaultValue);
                  }

                  if (newSource === "schema") {
                    field.onChange(fieldDefaultValue);
                  }
                };

                // const handleInputChange = (newValue) => {
                //   field.onChange({
                //     source: { type: "user" },
                //     value: newValue,
                //   });
                // };

                return (
                  <div className="flex items-center gap-2 px-2 py-4">
                    <div className="flex-grow">
                      {fieldData?.source?.type !== "source" && (
                        <DynamicField
                          name={name}
                          label={label}
                          description={description}
                          defaultValue={
                            fieldData?.source?.type === "source" ? sourceDefaultValue : defaultValue
                          }
                          rules={rules}
                          type={type}
                          attribute={attribute}
                          relationship={relationship}
                        />
                      )}

                      {fieldData?.source?.type === "source" && (
                        <div className="space-y-2">
                          <ConvertLabelFormField
                            label={label}
                            unique={unique}
                            required={!!rules?.required}
                            description={description}
                            kind={attribute?.kind ?? schemaKindLabel[relationship?.peer]}
                          />

                          <Row>
                            <FormInput>
                              <div className="grow">
                                {fieldData.source?.type === "source" && attribute && (
                                  <ConvertSourceAttributeInput
                                    objectDetailsData={objectDetailsData}
                                    sourceSchema={sourceSchema}
                                    mapping={mappings[name]}
                                    kind={attribute.kind}
                                    field={field}
                                  />
                                )}

                                {fieldData.source?.type === "source" &&
                                  relationship?.peer &&
                                  relationship.cardinality === "one" && (
                                    <ConvertSourceRelationshipOneInput
                                      objectDetailsData={objectDetailsData}
                                      sourceSchema={sourceSchema}
                                      mapping={mappings[name]}
                                      peer={relationship.peer}
                                      field={field}
                                    />
                                  )}

                                {fieldData.source?.type === "source" &&
                                  relationship?.peer &&
                                  relationship.cardinality === "many" && (
                                    <ConvertSourceRelationshipManyInput
                                      objectDetailsData={objectDetailsData}
                                      sourceSchema={sourceSchema}
                                      mapping={mappings[name]}
                                      peer={relationship.peer}
                                      field={field}
                                    />
                                  )}
                              </div>
                            </FormInput>
                          </Row>

                          <FormMessage />
                        </div>
                      )}
                    </div>

                    <RadioGroup
                      orientation="vertical"
                      value={fieldData?.source?.type === "source" ? "source" : "schema"}
                      onChange={(newValue) => {
                        return handleSourceChange(newValue);
                      }}
                      className="text-sm"
                    >
                      <Radio value="source">From source</Radio>
                      <Radio value="schema">Custom value</Radio>
                    </RadioGroup>
                  </div>
                );
              }}
            />
          );
        })}

        <div className="text-right">
          <FormSubmit>Convert</FormSubmit>
        </div>
      </div>
    </Form>
  );
};

export default ConvertFormWapper;
