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
import { Input } from "@/shared/components/inputs/input";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Form, FormField, FormInput, FormMessage, FormSubmit } from "@/shared/components/ui/form";

import { useConvertObjectMutation } from "@/entities/nodes/object/domain/convert-object.mutation";
import { useGetObjectConvertFieldsMapping } from "@/entities/nodes/object/domain/get-object-convert-fields-mapping.query";
import type { NodeObject } from "@/entities/nodes/types";
import { schemaKindNameState } from "@/entities/schema/stores/schemaKindName.atom";
import type { ModelSchema } from "@/entities/schema/types";

import { ALERT_TYPES, Alert } from "../ui/alert";

export type ConvertFormProps = {
  objectDetailsData: NodeObject;
  sourceSchema: ModelSchema;
  targetSchema: ModelSchema;
};

const ConvertForm = ({ objectDetailsData, sourceSchema, targetSchema }: ConvertFormProps) => {
  const navigate = useNavigate();

  const schemaKindLabel = useAtomValue(schemaKindNameState);
  const {
    data: mappings,
    isPending,
    error,
  } = useGetObjectConvertFieldsMapping({
    sourceKind: sourceSchema.kind!,
    targetKind: targetSchema.kind!,
  });

  const { mutateAsync: convertObject } = useConvertObjectMutation();

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
          console.log("result: ", result);
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
    <Form defaultValue={formDefaultValues} onSubmit={handleSubmit}>
      {fields.map(({ name, label, unique, description, rules, attribute, relationship }) => {
        const defaultValue = formDefaultValues[name];

        return (
          <FormField
            key={name}
            name={name}
            rules={rules}
            defaultValue={defaultValue}
            render={({ field }) => {
              const handleSourceChange = (newSource: string) => {
                if (newSource === "source") {
                  field.onChange({
                    source: { ...defaultValue?.source, type: "source" },
                    value: defaultValue?.value,
                  });
                }

                if (newSource === "custom") {
                  field.onChange({
                    source: { type: "schema" },
                    value: defaultValue?.value,
                  });
                }
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
                    value={field.value.source?.type === "source" ? "source" : "custom"}
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

                        {field.value.source?.type !== "source" && (
                          <Input {...field} onChange={handleInputValueChange} />
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
