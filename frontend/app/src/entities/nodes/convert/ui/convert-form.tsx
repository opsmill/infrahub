import { useState } from "react";
import { useFormContext } from "react-hook-form";
import { useNavigate } from "react-router";
import { toast } from "react-toastify";

import { constructPath } from "@/shared/api/rest/fetch";
import { Radio, RadioGroup } from "@/shared/components/aria/radio-group";
import { DynamicField } from "@/shared/components/form/dynamic-form";
import type { FormFieldValue } from "@/shared/components/form/type";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Form, FormSubmit } from "@/shared/components/ui/form";

import { useConvertObjectMutation } from "@/entities/nodes/convert/domain/convert-object.mutation";
import { useGetObjectConvertFieldsMapping } from "@/entities/nodes/convert/domain/get-object-convert-fields-mapping.query";
import { ConvertSourceField } from "@/entities/nodes/convert/ui/convert-source-field";
import type { NodeObject } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";

interface Mapping {
  is_mandatory: boolean;
  source_field_name: string | null;
  relationship_cardinality: string | null;
}

export default function ConvertFormWrapper({
  objectDetailsData,
  sourceSchema,
  targetSchema,
}: Omit<ConvertFormProps, "mappings">) {
  const {
    data: mappings,
    isPending,
    error,
  } = useGetObjectConvertFieldsMapping({
    sourceKind: sourceSchema.kind!,
    targetKind: targetSchema.kind!,
  });

  if (isPending) {
    return <LoadingIndicator className="p-4" />;
  }

  return (
    <ConvertForm
      mappings={error ? {} : mappings}
      objectDetailsData={objectDetailsData}
      sourceSchema={sourceSchema}
      targetSchema={targetSchema}
    />
  );
}

export interface ConvertFormProps {
  objectDetailsData: NodeObject;
  sourceSchema: ModelSchema;
  targetSchema: ModelSchema;
  mappings: Record<string, Mapping>;
}

function ConvertForm({
  mappings,
  objectDetailsData,
  sourceSchema,
  targetSchema,
}: ConvertFormProps) {
  const navigate = useNavigate();
  const { mutateAsync: convertObject } = useConvertObjectMutation();

  const fields = getFormFieldsFromSchema({
    schema: targetSchema,
    parentSchema: null,
    parentData: null,
  });

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
    <Form onSubmit={handleSubmit}>
      <div className="divide-y divide-gray-300">
        {fields.map((field) => {
          return (
            <ConvertFormField
              key={field.name}
              field={field}
              objectDetailsData={objectDetailsData}
              sourceSchema={sourceSchema}
              mapping={mappings[field.name]}
              sourceDefaultValue={sourceDefaultValues[field.name]}
            />
          );
        })}
      </div>

      <div className="-bottom-2 sticky border-gray-200 border-t bg-white p-2 text-right">
        <FormSubmit>Convert</FormSubmit>
      </div>
    </Form>
  );
}

interface ConvertFormFieldProps {
  field: any;
  mapping?: Mapping;
  objectDetailsData: NodeObject;
  sourceSchema: ModelSchema;
  sourceDefaultValue: any;
}

function ConvertFormField({
  field,
  mapping,
  objectDetailsData,
  sourceSchema,
  sourceDefaultValue,
}: ConvertFormFieldProps) {
  const hasMapping = !!mapping?.source_field_name;

  const [source, setSource] = useState(hasMapping ? "source" : "schema");
  const form = useFormContext();

  const handleSourceChange = (newSource: string) => {
    switch (newSource) {
      case "source":
        form.setValue(field.name, sourceDefaultValue, { shouldValidate: true });
        break;
      case "schema":
        form.setValue(field.name, field.defaultValue, { shouldValidate: true });
        break;
    }

    setSource(newSource);
  };

  return (
    <div className="flex items-center gap-4 px-2 py-4">
      <div className="grow">
        {source === "source" ? (
          <ConvertSourceField
            {...field}
            objectDetailsData={objectDetailsData}
            sourceSchema={sourceSchema}
            mapping={mapping}
            defaultValue={sourceDefaultValue}
          />
        ) : (
          <DynamicField {...field} />
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
}
