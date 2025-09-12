import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import DynamicForm from "./dynamic-form";
import { getFormFieldsFromSchema } from "./utils/getFormFieldsFromSchema";

export type ConvertFormProps = {
  kind: string;
};

const ConvertForm = ({ kind }: ConvertFormProps) => {
  const { schema } = useSchema(kind);
  const fields = getFormFieldsFromSchema({ schema });
  return <DynamicForm fields={fields} />;
};

export default ConvertForm;
