import { useAtomValue } from "jotai";
import { useState } from "react";
import { useFormContext } from "react-hook-form";
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
import type { FormFieldValue } from "./type";

interface Mapping {
  is_mandatory: boolean;
  source_field_name: string | null;
  relationship_cardinality: string | null;
}

export type ConvertFormProps = {
  objectDetailsData: NodeObject;
  sourceSchema: ModelSchema;
  targetSchema: ModelSchema;
  mappings: Record<string, Mapping>;
};

const ConvertFormWrapper = ({
  objectDetailsData,
  sourceSchema,
  targetSchema,
}: ConvertFormProps) => {
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

  const formDefaultValues: Record<string, FormFieldValue> = fields.reduce((acc, field) => {
    return { ...acc, [field.name]: field.defaultValue };
  }, {});

  const sourceDefaultValues: Record<string, FormFieldValue> = fields.reduce((acc, field) => {
    const hasMapping = !!mappings[field.name]?.source_field_name;
    const fieldData = objectDetailsData[field.name];

    if (!hasMapping) {
      return { ...acc, [field.name]: field.defaultValue };
    }

    // Relationship many
    if (fieldData && "edges" in fieldData) {
      const nodes = fieldData?.edges
        ?.map((edge) => edge.node)
        .filter((node) => {
          return node != null;
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
    if (fieldData && "node" in fieldData) {
      return {
        ...acc,
        [field.name]: {
          source: {
            type: "source",
            label: field.label,
            name: field.name,
          },
          value: fieldData.node,
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
        value: fieldData && "value" in fieldData ? fieldData.value : undefined,
      },
    };
  }, {});

  const handleSubmit = async (formData: { [key: string]: FormFieldValue }) => {
    const fieldsMapping = fields.reduce((acc, field) => {
      const fieldData = formData[field.name];

      if (fieldData?.source?.type === "source") {
        return {
          ...acc,
          [field.name]: {
            source_field: fieldData.source.name,
          },
        };
      }

      if (Array.isArray(fieldData?.value)) {
        return {
          ...acc,
          [field.name]: {
            data: { peer_ids: fieldData.value },
          },
        };
      }

      if (fieldData?.source?.node) {
        return {
          ...acc,
          [field.name]: {
            data: { peer_id: fieldData.value },
          },
        };
      }

      if (fieldData?.value) {
        return {
          ...acc,
          [field.name]: {
            data: { attribute_value: fieldData.value },
          },
        };
      }

      return {
        ...acc,
        [field.name]: {
          use_default_value: true,
        },
      };
    }, {});

    if (!objectDetailsData.id || !targetSchema.kind) {
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message="Missing required object ID or target kind for conversion"
        />
      );
      return;
    }

    await convertObject(
      {
        nodeId: objectDetailsData.id as string,
        targetKind: targetSchema.kind as string,
        fieldsMapping,
      },
      {
        onSuccess: async (result) => {
          toast(<Alert type={ALERT_TYPES.SUCCESS} message="Object converted!" />);
          const path = constructPath(`/objects/${targetSchema.kind}/${result.id}`);

          navigate(path);
        },
        onError: (error) => {
          console.error("Error when retrieving mappings: ", error);
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
    <Form onSubmit={handleSubmit} className="relative">
      <div className="divide-y divide-gray-300">
        {fields.map((field) => {
          return (
            <ConvertFieldWrapper
              key={field.name}
              field={field}
              objectDetailsData={objectDetailsData}
              sourceSchema={sourceSchema}
              mapping={mappings[field.name]}
              sourceDefaultValue={sourceDefaultValues[field.name]}
              formDefaultValue={formDefaultValues[field.name]}
            />
          );
        })}
      </div>

      <div className="sticky bottom-0 rounded-b-md bg-white p-2 text-right">
        <FormSubmit>Convert</FormSubmit>
      </div>
    </Form>
  );
};

type ConvertFieldWrapperProps = {
  field: any;
  mapping?: Mapping;
  objectDetailsData: NodeObject;
  sourceSchema: ModelSchema;
  sourceDefaultValue: any;
  formDefaultValue: any;
};

const ConvertFieldWrapper = ({
  field,
  mapping,
  objectDetailsData,
  sourceSchema,
  sourceDefaultValue,
  formDefaultValue,
}: ConvertFieldWrapperProps) => {
  const hasMapping = !!mapping?.source_field_name;

  const [source, setSource] = useState(hasMapping ? "source" : "schema");
  const form = useFormContext();

  const handleSourceChange = (newSource: string) => {
    setSource(newSource);

    form.resetField(field.name);
  };

  return (
    <div className="flex items-center gap-4 px-2 py-4">
      <div className="flex-grow">
        {source !== "source" && <DynamicField {...field} defaultValue={formDefaultValue} />}

        {source === "source" && (
          <ConvertSourceField
            {...field}
            objectDetailsData={objectDetailsData}
            sourceSchema={sourceSchema}
            mapping={mapping}
            defaultValue={sourceDefaultValue}
          />
        )}
      </div>

      <RadioGroup
        orientation="vertical"
        value={source}
        onChange={handleSourceChange}
        className="text-sm"
        aria-label="Select source"
      >
        <Radio value="source">From source</Radio>
        <Radio value="schema">Custom value</Radio>
      </RadioGroup>
    </div>
  );
};

type ConvertSourceFieldProps = {
  objectDetailsData: NodeObject;
  sourceSchema: ModelSchema;
  mapping: any;
  name: string;
  label: string;
  unique?: boolean;
  description?: string;
  rules?: any;
  attribute?: any;
  relationship?: any;
  defaultValue?: any;
};

const ConvertSourceField = ({
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
}: ConvertSourceFieldProps) => {
  const schemaKindLabel = useAtomValue(schemaKindNameState);

  return (
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
                  {attribute && (
                    <ConvertSourceAttributeInput
                      objectDetailsData={objectDetailsData}
                      sourceSchema={sourceSchema}
                      mapping={mapping}
                      kind={attribute.kind}
                      field={field}
                    />
                  )}

                  {relationship?.peer && relationship.cardinality === "one" && (
                    <ConvertSourceRelationshipOneInput
                      objectDetailsData={objectDetailsData}
                      sourceSchema={sourceSchema}
                      mapping={mapping}
                      peer={relationship.peer}
                      field={field}
                    />
                  )}

                  {relationship?.peer && relationship.cardinality === "many" && (
                    <ConvertSourceRelationshipManyInput
                      objectDetailsData={objectDetailsData}
                      sourceSchema={sourceSchema}
                      mapping={mapping}
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
  );
};

export default ConvertFormWrapper;
