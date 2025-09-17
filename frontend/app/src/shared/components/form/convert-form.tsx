import { useFieldsMappingTypeConversion } from "@/entities/nodes/object/domain/get-convert-fields-mappings.query";
import { NodeObject } from "@/entities/nodes/types";
import { ModelSchema } from "@/entities/schema/types";

import ErrorScreen from "../errors/error-screen";
import { LoadingIndicator } from "../loading/loading-indicator";
import { Form, FormSubmit } from "../ui/form";
import { DynamicField } from "./dynamic-form";
import { getFormFieldsFromSchema } from "./utils/getFormFieldsFromSchema";

export type ConvertFormProps = {
  objectDetailsData: NodeObject;
  sourceSchema: ModelSchema;
  targetSchema: ModelSchema;
};

const ConvertForm = ({ sourceSchema, targetSchema }: ConvertFormProps) => {
  const { isPending, error } = useFieldsMappingTypeConversion({
    sourceKind: sourceSchema.kind,
    targetKind: targetSchema.kind,
  });

  const fields = getFormFieldsFromSchema({ schema: targetSchema });

  if (isPending) {
    return <LoadingIndicator />;
  }

  if (error) {
    return <ErrorScreen message="An error occurred while fetching the fields mapping" />;
  }

  const formDefaultValues = fields.reduce(
    (acc, field) => ({ ...acc, [field.name]: field.defaultValue }),
    {}
  );

  return (
    <Form defaultValues={formDefaultValues}>
      {fields.map((field) => (
        <DynamicField key={`${field.type}_${field.name}`} {...field} />
      ))}

      <div className="text-right">
        <FormSubmit>Convert</FormSubmit>
      </div>
    </Form>
  );
};

export default ConvertForm;
