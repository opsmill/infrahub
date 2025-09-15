import { useFieldsMappingTypeConversion } from "@/entities/nodes/object/domain/get-fields-mapping-type-conversion.query";
import { NodeObject } from "@/entities/nodes/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import ErrorScreen from "../errors/error-screen";
import { LoadingIndicator } from "../loading/loading-indicator";
import DynamicForm from "./dynamic-form";
import { getFormFieldsFromSchema } from "./utils/getFormFieldsFromSchema";

export type ConvertFormProps = {
  objectDetailsData: NodeObject;
  sourceKind: string;
  targetKind: string;
};

const ConvertForm = ({ sourceKind, targetKind }: ConvertFormProps) => {
  const { isPending, error } = useFieldsMappingTypeConversion({
    sourceKind,
    targetKind,
  });

  const { schema } = useSchema(targetKind);

  if (!schema) {
    return <LoadingIndicator message="Loading schema..." />;
  }

  const fields = getFormFieldsFromSchema({ schema });

  if (isPending) {
    return <LoadingIndicator />;
  }

  if (error) {
    return <ErrorScreen message="An error occurred while fetching the fields mapping" />;
  }

  return <DynamicForm fields={fields} />;
};

export default ConvertForm;
