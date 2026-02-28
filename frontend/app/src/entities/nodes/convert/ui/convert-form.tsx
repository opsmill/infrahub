import { useNavigate } from "react-router";
import { toast } from "react-toastify";

import type { FormFieldValue } from "@/shared/components/form/type";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Form, FormSubmit } from "@/shared/components/ui/form";

import type { ConvertFieldMapping, ConvertFormFieldValue } from "@/entities/nodes/convert/types";
import { ConvertFormField } from "@/entities/nodes/convert/ui/convert-form-field";
import { useConvertObjectMutation } from "@/entities/nodes/convert/ui/queries/convert-object.mutation";
import { useGetObjectConvertFieldsMapping } from "@/entities/nodes/convert/ui/queries/get-object-convert-fields-mapping.query";
import { getFieldsMappingPayload } from "@/entities/nodes/convert/utils/get-fields-mapping-payload";
import type { NodeObject } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
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
    const fieldsMapping = getFieldsMappingPayload(fields, formData);

    await convertObject(
      {
        nodeId: sourceObject.id,
        targetKind: targetSchema.kind!,
        fieldsMapping,
      },
      {
        onSuccess: async (result) => {
          toast(
            <Alert
              type={ALERT_TYPES.SUCCESS}
              message={`Successfully converted ${sourceSchema.label} to ${targetSchema.label}`}
            />
          );
          const path = getObjectDetailsUrl(targetSchema.kind!, result.id);

          navigate(path);
        },
        onError: (error) => {
          console.error("Error during object conversion: ", error);
          toast(<Alert type={ALERT_TYPES.ERROR} message={error.message} />);
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

      <div className="sticky -bottom-2 border-gray-200 border-t bg-white p-2 text-right">
        <FormSubmit>Convert</FormSubmit>
      </div>
    </Form>
  );
}
