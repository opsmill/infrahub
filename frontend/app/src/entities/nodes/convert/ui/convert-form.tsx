import { useNavigate } from "react-router";
import { toast } from "react-toastify";

import { constructPath } from "@/shared/api/rest/fetch";
import type { FormFieldValue } from "@/shared/components/form/type";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Form, FormSubmit } from "@/shared/components/ui/form";

import { useConvertObjectMutation } from "@/entities/nodes/convert/domain/convert-object.mutation";
import { useGetObjectConvertFieldsMapping } from "@/entities/nodes/convert/domain/get-object-convert-fields-mapping.query";
import type { ConvertFieldMapping, ConvertFormFieldValue } from "@/entities/nodes/convert/types";
import { ConvertFormField } from "@/entities/nodes/convert/ui/convert-form-field";
import type { NodeObject } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";

export default function ConvertFormWrapper({
  sourceObject,
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
      sourceObject={sourceObject}
      sourceSchema={sourceSchema}
      targetSchema={targetSchema}
    />
  );
}

export interface ConvertFormProps {
  sourceObject: NodeObject;
  sourceSchema: ModelSchema;
  targetSchema: ModelSchema;
  mappings: Record<string, ConvertFieldMapping>;
}

function ConvertForm({ mappings, sourceObject, sourceSchema, targetSchema }: ConvertFormProps) {
  const navigate = useNavigate();
  const { mutateAsync: convertObject } = useConvertObjectMutation();

  const fields = getFormFieldsFromSchema({
    schema: targetSchema,
    parentSchema: null,
    parentData: null,
  });

  const handleSubmit = async (formData: {
    [key: string]: FormFieldValue | ConvertFormFieldValue;
  }) => {
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

      if (Array.isArray(fieldData?.value) && field.type !== "List") {
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

    if (!sourceObject.id || !targetSchema.kind) {
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
        nodeId: sourceObject.id as string,
        targetKind: targetSchema.kind as string,
        fieldsMapping,
      },
      {
        onSuccess: async (result) => {
          toast(<Alert type={ALERT_TYPES.SUCCESS} message="Object converted!" />);
          const path = constructPath(`/objects/${targetSchema.kind}/${result.id}`);

          navigate(path);
        },
      }
    );
  };

  return (
    <Form onSubmit={handleSubmit} className="divide-y divide-gray-300">
      {fields.map((field) => {
        return (
          <ConvertFormField
            key={field.name}
            field={field}
            sourceObject={sourceObject}
            sourceSchema={sourceSchema}
            conversionMapping={mappings[field.name]}
          />
        );
      })}

      <div className="-bottom-2 sticky border-gray-200 border-t bg-white p-2 text-right">
        <FormSubmit>Convert</FormSubmit>
      </div>
    </Form>
  );
}
