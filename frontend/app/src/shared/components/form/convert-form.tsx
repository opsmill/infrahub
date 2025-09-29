import { useAtomValue } from "jotai";
import { useForm } from "react-hook-form";
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

  const schemaKindLabel = useAtomValue(schemaKindNameState);

  const { mutateAsync: convertObject } = useConvertObjectMutation();

  const fields = getFormFieldsFromSchema({
    schema: targetSchema,
    parentSchema: null,
    parentData: null,
  });

  const formDefaultValues = fields.reduce((acc, field) => {
    const hasMapping = !!mappings[field.name]?.source_field_name;

    if (hasMapping) {
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
    }

    return { ...acc, [field.name]: field.defaultValue };
  }, {});

  const form = useForm({ defaultValues: formDefaultValues });

  const handleSubmit = async (formData) => {
    const fieldsMapping = Object.entries(formData).reduce((acc, [fieldName, fieldData]) => {
      if (fieldData.source.type === "source") {
        return {
          ...acc,
          [fieldName]: {
            source_field: fieldData.source.name,
          },
        };
      }

      if (fieldData.source.type === "schema") {
        return {
          ...acc,
          [fieldName]: {
            use_default_value: true,
          },
        };
      }

      if (Array.isArray(fieldData.value)) {
        return {
          ...acc,
          [fieldName]: {
            peer_ids: fieldData.value,
          },
        };
      }

      if (fieldData.source.node) {
        return {
          ...acc,
          [fieldName]: {
            peer_id: fieldData.value,
          },
        };
      }

      return {
        ...acc,
        [fieldName]: {
          attribute_value: fieldData.value,
        },
      };
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
    <Form form={form} onSubmit={handleSubmit}>
      <div className="divide-y divide-gray-300">
        {fields.map((fieldProps) => {
          const { name, label, unique, description, rules, attribute, relationship } = fieldProps;

          const defaultValue = formDefaultValues[name];

          const currentField = form.watch(name);

          const handleSourceChange = (newSource: string) => {
            if (newSource === "source") {
              form.setValue(name, {
                source: { ...defaultValue?.source, type: "source" },
                value: defaultValue?.value,
              });
            }

            if (newSource === "schema") {
              form.setValue(name, {
                source: { type: "schema" },
                value: defaultValue?.value,
              });
            }
          };

          const handleInputChange = (newValue) => {
            form.setValue(name, {
              source: { type: "user" },
              value: newValue,
            });
          };

          return (
            <div key={name} className="flex items-center gap-2 px-2 py-4">
              <div className="flex-grow">
                {currentField?.source?.type !== "source" && (
                  <DynamicField {...fieldProps} onChange={handleInputChange} />
                )}

                {currentField?.source?.type === "source" && (
                  <FormField
                    name={name}
                    rules={rules}
                    defaultValue={defaultValue}
                    render={({ field }) => {
                      return (
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
                                {field.value.source?.type === "source" && attribute && (
                                  <ConvertSourceAttributeInput
                                    objectDetailsData={objectDetailsData}
                                    sourceSchema={sourceSchema}
                                    mapping={mappings?.[field.name]}
                                    kind={attribute.kind}
                                    field={field}
                                  />
                                )}

                                {field.value.source?.type === "source" &&
                                  relationship?.peer &&
                                  relationship.cardinality === "one" && (
                                    <ConvertSourceRelationshipOneInput
                                      objectDetailsData={objectDetailsData}
                                      sourceSchema={sourceSchema}
                                      mapping={mappings?.[field.name]}
                                      peer={relationship.peer}
                                      field={field}
                                    />
                                  )}

                                {field.value.source?.type === "source" &&
                                  relationship?.peer &&
                                  relationship.cardinality === "many" && (
                                    <ConvertSourceRelationshipManyInput
                                      objectDetailsData={objectDetailsData}
                                      sourceSchema={sourceSchema}
                                      mapping={mappings?.[field.name]}
                                      peer={relationship.peer}
                                      field={field}
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
                )}
              </div>

              <RadioGroup
                orientation="vertical"
                value={currentField?.source?.type === "source" ? "source" : "schema"}
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
        })}

        <div className="text-right">
          <FormSubmit>Convert</FormSubmit>
        </div>
      </div>
    </Form>
  );
};

export default ConvertFormWapper;
