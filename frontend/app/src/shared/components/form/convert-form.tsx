import { useFieldsMappingTypeConversion } from "@/entities/nodes/object/domain/get-convert-fields-mappings.query";
import { NodeObject } from "@/entities/nodes/types";
import { ModelSchema } from "@/entities/schema/types";

import ErrorScreen from "../errors/error-screen";
import { LoadingIndicator } from "../loading/loading-indicator";
import DynamicForm from "./dynamic-form";
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

  return <DynamicForm fields={fields} />;
};

export default ConvertForm;
